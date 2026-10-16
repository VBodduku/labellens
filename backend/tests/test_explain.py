from __future__ import annotations

import asyncio
import json

import pytest

from backend.app.errors import ApiError
from backend.app.llm.base import ProviderUnavailableError
from backend.app.llm.router import LLMRouter
from backend.app.pipeline import explain as explain_module
from backend.app.pipeline.explain import ExplainCache, explain
from backend.tests.fakes import FakeLLM
from shared.contract import ExplainResponse


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(explain_module, "EXPLAIN_CACHE", ExplainCache())


def run(term: str, lang: str, llm: FakeLLM) -> ExplainResponse:
    return asyncio.run(explain(term, lang, LLMRouter([llm], 5)))  # type: ignore[arg-type]


def test_kb_term_in_english_needs_no_llm() -> None:
    llm = FakeLLM()
    response = run("INS 322", "en", llm)
    assert response.source == "kb" and response.canonical_id and llm.prompts == []


def test_kb_term_is_translated_for_hindi_and_cached() -> None:
    llm = FakeLLM([json.dumps({"description": "हिंदी विवरण", "caution": None})])
    first = run("INS 322", "hi", llm)
    second = run("ins 322", "hi", llm)
    assert first.source == "kb" and first.description == "हिंदी विवरण"
    assert second == first and len(llm.prompts) == 1
    assert "Hindi" in llm.prompts[0]


def test_kb_term_keeps_english_when_translation_fails() -> None:
    response = run("INS 322", "te", FakeLLM([ProviderUnavailableError("down")]))
    assert response.source == "kb" and response.description


def test_unknown_term_uses_llm_with_filtered_categories_and_note() -> None:
    answer = {"display_name": "Zorbex", "description": "A thickener that can be made from different sources.",
              "origin": "varies", "categories": ["milk", "wizard_dust"], "caution": "Source may vary."}
    response = run("Zorbex", "en", FakeLLM([json.dumps(answer)]))
    assert response.source == "llm" and response.categories == ["milk"]
    assert response.caution is not None and "not from our checked database" in response.caution


def test_unknown_term_without_llm_is_503() -> None:
    with pytest.raises(ApiError) as info:
        run("Zorbex", "en", FakeLLM([ProviderUnavailableError("down")]))
    assert info.value.status == 503 and info.value.error_code == "LLM_UNAVAILABLE"


def test_llm_explanation_with_banned_words_is_refused() -> None:
    answer = {"display_name": "Zorbex", "description": "Completely safe and healthy.", "origin": "plant",
              "categories": [], "caution": None}
    with pytest.raises(ApiError):
        run("Zorbex", "en", FakeLLM([json.dumps(answer)]))
