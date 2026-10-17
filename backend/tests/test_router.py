from __future__ import annotations

import asyncio
import time
import json

import pytest

from backend.app.llm.base import (
    AccessDeniedError,
    InvalidOutputError,
    LLMImage,
    ModelOverloadedError,
    ProviderUnavailableError,
    RateLimitedError,
)
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.pipeline.llm_schema import LLMExtraction
from backend.tests.fakes import FakeLLM, recorded

GOOD = recorded("ollama_test_label.json")


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def run(router: LLMRouter):  # type: ignore[no-untyped-def]
    return asyncio.run(router.generate(lambda provider: f"prompt for {provider}", [], LLMExtraction))


def test_first_provider_answers() -> None:
    primary, ollama = FakeLLM([GOOD]), FakeLLM([GOOD], name="ollama")
    result = run(LLMRouter([primary, ollama], 5))
    assert (result.provider, result.attempts) == ("gemini", 1)
    assert primary.prompts == ["prompt for gemini"] and ollama.prompts == []
    assert "$ref" not in json.dumps(primary.schemas[0])


def test_rate_limit_cools_down_and_falls_through_to_backup_then_ollama() -> None:
    clock = Clock()
    primary = FakeLLM([RateLimitedError(30)], label="gemini:primary")
    backup = FakeLLM([RateLimitedError(10)], label="gemini:backup")
    ollama = FakeLLM([GOOD], name="ollama", model="gemma3:4b")
    router = LLMRouter([primary, backup, ollama], 5, clock=clock)
    result = run(router)
    assert (result.provider, result.model, result.attempts) == ("ollama", "gemma3:4b", 3)
    assert ollama.prompts == ["prompt for ollama"]
    assert router.provider_status() == {"gemini": False, "ollama": True}

    run(router)                                     # still cooling down: primary and backup skipped
    assert len(primary.prompts) == 1 and len(backup.prompts) == 1
    clock.now += 11
    assert router.provider_status()["gemini"] is True


def test_a_callers_budget_covers_the_whole_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.llm.router.MIN_ATTEMPT_S", 0.05)
    slow, next_one = FakeLLM([GOOD], delay_s=1.0), FakeLLM([GOOD], label="gemini:lite", delay_s=1.0)
    started = time.monotonic()
    with pytest.raises(AllProvidersFailedError):
        asyncio.run(LLMRouter([slow, next_one], 5).generate(lambda p: "x", [], LLMExtraction, timeout_s=0.3))
    assert time.monotonic() - started < 0.5                            # no fresh 0.3 s for the next model
    assert len(slow.prompts) == 1 and len(next_one.prompts) == 1       # hedged inside the same budget


def test_an_overloaded_model_that_is_slow_to_say_so_does_not_starve_the_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seen live: gemini-3.5-flash took ~30 s to return its 503, leaving the fallbacks a few seconds."""
    monkeypatch.setattr("backend.app.llm.router.MIN_ATTEMPT_S", 0.05)
    overloaded = FakeLLM([ModelOverloadedError(60)], label="gemini:primary:main", delay_s=2.0)
    lite = FakeLLM([GOOD], label="gemini:primary:lite", model="lite", delay_s=0.1)
    started = time.monotonic()
    result = asyncio.run(LLMRouter([overloaded, lite], 5).generate(lambda p: "x", [], LLMExtraction, timeout_s=1.0))
    assert result.model == "lite"
    assert time.monotonic() - started < 1.0                            # answered at ~0.7 s, not after the 503


def test_a_model_that_answers_in_time_costs_no_extra_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.llm.router.MIN_ATTEMPT_S", 0.05)
    quick = FakeLLM([GOOD], label="gemini:primary:main", delay_s=0.05)
    lite = FakeLLM([GOOD], label="gemini:primary:lite", model="lite")
    result = asyncio.run(LLMRouter([quick, lite], 5).generate(lambda p: "x", [], LLMExtraction, timeout_s=1.0))
    assert result.model == quick.model and lite.prompts == []


def test_a_slow_model_that_answers_first_still_wins_and_the_spare_call_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("backend.app.llm.router.MIN_ATTEMPT_S", 0.05)
    slow = FakeLLM([GOOD], label="gemini:primary:main", delay_s=0.45)
    spare = FakeLLM([GOOD], label="gemini:primary:lite", model="lite", delay_s=2.0)
    started = time.monotonic()
    result = asyncio.run(LLMRouter([slow, spare], 5).generate(lambda p: "x", [], LLMExtraction, timeout_s=0.6))
    assert result.model == slow.model and len(spare.prompts) == 1     # spare started at 0.36 s, then cancelled
    assert time.monotonic() - started < 0.6


def test_without_a_budget_models_are_tried_one_after_another() -> None:
    down = FakeLLM([ProviderUnavailableError("down")], label="gemini:primary:main", delay_s=0.05)
    lite = FakeLLM([GOOD], label="gemini:primary:lite", model="lite")
    assert run(LLMRouter([down, lite], 5)).model == "lite" and len(down.prompts) == 1


def test_overloaded_model_is_skipped_for_its_cooldown_without_counting_as_rate_limit() -> None:
    clock = Clock()
    main = FakeLLM([ModelOverloadedError(60), GOOD], label="gemini:primary:main")
    lite = FakeLLM([GOOD, GOOD], label="gemini:primary:lite", model="lite")
    router = LLMRouter([main, lite], 5, clock=clock)
    assert run(router).model == "lite"
    assert run(router).model == "lite" and len(main.prompts) == 1      # overloaded model not asked again
    clock.now += 61
    assert run(router).model == main.model


def test_a_refused_key_skips_every_model_on_it_and_falls_to_the_next_key() -> None:
    clock = Clock()
    main = FakeLLM([AccessDeniedError(600), GOOD], label="gemini:primary:main")
    lite = FakeLLM([GOOD], label="gemini:primary:lite", model="lite")
    backup = FakeLLM([GOOD, GOOD], label="gemini:backup:main", model="backup")
    router = LLMRouter([main, lite, backup], 5, clock=clock)
    assert run(router).model == "backup" and lite.prompts == []       # same key, never asked
    assert run(router).model == "backup" and len(main.prompts) == 1
    assert router.provider_status()["gemini"] is True                   # the backup key still works
    clock.now += 601
    assert run(router).model == main.model


def test_a_refused_only_key_reports_gemini_down() -> None:
    router = LLMRouter([FakeLLM([AccessDeniedError(600)], label="gemini:primary:main"),
                        FakeLLM([GOOD], label="gemini:primary:lite")], 5)
    with pytest.raises(AllProvidersFailedError) as info:
        run(router)
    assert info.value.rate_limited is False and router.provider_status()["gemini"] is False


def test_only_overloaded_models_is_not_reported_as_rate_limited() -> None:
    with pytest.raises(AllProvidersFailedError) as info:
        run(LLMRouter([FakeLLM([ModelOverloadedError(60)])], 5))
    assert info.value.rate_limited is False


def test_invalid_json_gets_one_repair_attempt() -> None:
    primary = FakeLLM(['{"panels": "nope"}', GOOD])
    result = run(LLMRouter([primary], 5))
    assert result.attempts == 2
    assert "did not match the required JSON schema" in primary.prompts[1]
    assert "panels" in primary.prompts[1]


def test_still_invalid_after_repair_falls_through() -> None:
    primary, ollama = FakeLLM(["not json", "{}"]), FakeLLM([GOOD], name="ollama")
    result = run(LLMRouter([primary, ollama], 5))
    assert result.provider == "ollama" and len(primary.prompts) == 2


def test_timeout_and_errors_fall_through() -> None:
    slow = FakeLLM([GOOD], delay_s=1.0)
    broken = FakeLLM([ProviderUnavailableError("down")], label="gemini:backup")
    empty = FakeLLM([InvalidOutputError("empty")], name="ollama")
    with pytest.raises(AllProvidersFailedError) as info:
        asyncio.run(LLMRouter([slow, broken, empty], 0.05).generate(lambda p: "x", [], LLMExtraction))
    assert info.value.rate_limited is False and info.value.retry_after_s is None


def test_all_rate_limited_reports_shortest_retry() -> None:
    router = LLMRouter([FakeLLM([RateLimitedError(40)]), FakeLLM([RateLimitedError(12)], name="ollama")], 5)
    with pytest.raises(AllProvidersFailedError) as info:
        run(router)
    assert info.value.rate_limited is True and info.value.retry_after_s == 12


def test_provider_too_slow_for_images_is_skipped_for_image_calls_only() -> None:
    clock = Clock()
    slow = FakeLLM([GOOD], name="ollama", delay_s=1.0)
    router = LLMRouter([slow], 0.05, clock=clock)
    image = [LLMImage("image/jpeg", b"x")]
    for _ in range(2):
        with pytest.raises(AllProvidersFailedError):
            asyncio.run(router.generate(lambda p: "x", image, LLMExtraction))
    assert len(slow.prompts) == 1                                   # second image call skipped
    slow.delay_s = 0
    assert asyncio.run(router.generate(lambda p: "x", [], LLMExtraction)).provider == "ollama"   # text still ok
    assert router.provider_status()["ollama"] is True
    clock.now += 301
    asyncio.run(router.generate(lambda p: "x", image, LLMExtraction))
    assert len(slow.prompts) == 3


def test_short_caller_budget_timeout_does_not_cool_down() -> None:
    slow = FakeLLM([GOOD], name="ollama", delay_s=1.0)
    router = LLMRouter([slow], 5)
    with pytest.raises(AllProvidersFailedError):
        asyncio.run(router.generate(lambda p: "x", [], LLMExtraction, timeout_s=0.05))
    assert router.provider_status()["ollama"] is True


def test_each_key_gets_main_then_fallback_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.config import get_settings
    from backend.app.llm.router import gemini_clients

    monkeypatch.setenv("GEMINI_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", "k2")
    monkeypatch.setenv("GEMINI_MODEL", "main-model")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "lite-model")
    get_settings.cache_clear()
    assert [(c.label, c.model) for c in gemini_clients()] == [
        ("gemini:primary:main-model", "main-model"), ("gemini:primary:lite-model", "lite-model"),
        ("gemini:backup:main-model", "main-model"), ("gemini:backup:lite-model", "lite-model")]
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "main-model")
    get_settings.cache_clear()
    assert len(gemini_clients()) == 2
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", "")
    monkeypatch.setenv("GEMINI_FALLBACK_MODEL", "older-model, lite-model,")
    get_settings.cache_clear()
    assert [c.model for c in gemini_clients()] == ["main-model", "older-model", "lite-model"]


def test_an_unusable_answer_gets_one_repair_then_the_next_model() -> None:
    empty, lite = FakeLLM([GOOD, GOOD], label="gemini:primary:main"), FakeLLM([GOOD], label="gemini:primary:lite", model="lite")
    seen: list[str] = []

    def check(value: LLMExtraction) -> str | None:
        seen.append("checked")
        return "empty" if len(seen) <= 2 else None              # the first model's answer and its repair are rejected

    result = asyncio.run(LLMRouter([empty, lite], 5).generate(lambda p: "x", [], LLMExtraction, check=check))
    assert result.model == "lite" and len(empty.prompts) == 2
    assert "- empty" in empty.prompts[1]                        # the repair prompt says what was wrong


def test_a_backup_that_fails_at_once_passes_its_turn_on_without_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seen live: the second model was out of quota (instant 429) while the first was still hanging."""
    monkeypatch.setattr("backend.app.llm.router.MIN_ATTEMPT_S", 0.05)
    hanging = FakeLLM([GOOD], label="gemini:primary:main", delay_s=5.0)
    no_quota = FakeLLM([RateLimitedError(69072)], label="gemini:primary:flash")
    lite = FakeLLM([GOOD], label="gemini:primary:lite", model="lite", delay_s=0.1)
    started = time.monotonic()
    result = asyncio.run(LLMRouter([hanging, no_quota, lite], 5).generate(lambda p: "x", [], LLMExtraction, timeout_s=1.0))
    assert result.model == "lite"
    assert time.monotonic() - started < 0.8                    # lite started right after the 429, at ~0.5 s
