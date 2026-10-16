from __future__ import annotations

import asyncio
import json

import pytest

from backend.app.llm.base import InvalidOutputError, ProviderUnavailableError, RateLimitedError
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
