from __future__ import annotations

import asyncio
import json

import pytest

from backend.tests import fixture_data as fixtures
from backend.app.llm.base import ProviderUnavailableError
from backend.app.llm.router import LLMRouter
from backend.app.pipeline import summarize
from backend.app.pipeline.interpret import interpret
from backend.app.pipeline.summarize import valid_summary
from backend.app.wording import has_banned_word
from backend.tests.fakes import INTERPRET, SUMMARIZE, FakeLLM
from shared.contract import Profile
from shared.engine_interface import UnresolvedTerm

PROFILES = [Profile.model_validate(p)
            for p in json.loads((fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))]
REPORTS = fixtures.scan_result().reports


def terms(*names: str) -> list[UnresolvedTerm]:
    return [UnresolvedTerm(ingredient_id=f"ing_{n}", term=t) for n, t in enumerate(names)]


def test_interpretations_keep_only_vocabulary_categories_and_known_terms() -> None:
    answer = {"interpretations": [
        {"term": "natural flavours", "categories": ["milk", "dairy", "unicorn"], "origin": "varies",
         "confidence": 1.4, "rationale": "Flavourings may be dairy-derived."},
        {"term": "Mystery Paste", "categories": ["not_a_category"], "origin": "unknown", "confidence": 0.2,
         "rationale": "Unknown."},
        {"term": "something we never asked", "categories": ["egg"], "origin": "animal", "confidence": 0.9,
         "rationale": "x"}]}
    llm = FakeLLM(routes={INTERPRET: [json.dumps(answer)]})
    result = asyncio.run(interpret(terms("Natural Flavours", "Mystery Paste", "natural flavours"), LLMRouter([llm], 5)))
    assert list(result) == ["Natural Flavours"]
    assert result["Natural Flavours"].categories == ["milk", "dairy"]
    assert result["Natural Flavours"].confidence == 1.0
    prompt = llm.prompts[0]
    assert "peanut" in prompt and prompt.count("- Natural Flavours") == 1 and "Mystery Paste" in prompt


def test_interpretation_caps_terms_and_survives_llm_failure() -> None:
    llm = FakeLLM([ProviderUnavailableError("down")])
    assert asyncio.run(interpret(terms(*[f"term {n}" for n in range(15)]), LLMRouter([llm], 5))) is None
    assert llm.prompts[0].count("- term ") == 10
    assert asyncio.run(interpret([], LLMRouter([llm], 5))) == {}


@pytest.mark.parametrize("text", [
    "Not listed: this bar looks safe for Lakshmi.",
    "Healthy choice for Aarav.",
    "यह सुरक्षित है।",
    "ఇది సురక్షితం.",
    "Probably fine for Thatha.",
])
def test_banned_words_in_any_language(text: str) -> None:
    assert has_banned_word(text) and not valid_summary(text)


def test_banned_word_matching_is_by_whole_word() -> None:
    assert not has_banned_word("Check this: unsafety of reading is unclear; safeguard text.")
    assert valid_summary("Conflict: contains Peanuts (22%).")
    assert not valid_summary(" ".join(["word"] * 26))


def test_summaries_dropped_when_invalid_or_unknown_profile() -> None:
    answer = {"summaries": [
        {"profile_id": "p_aarav", "summary": "విరుద్ధం: Peanuts (22%) పదార్థాల జాబితాలో ఉన్నాయి."},
        {"profile_id": "p_thatha", "summary": "Healthy enough for Thatha."},
        {"profile_id": "p_lakshmi", "summary": "జాబితాలో లేదు: Natural Flavours."},     # wrong state word
        {"profile_id": "p_ghost", "summary": "విరుద్ధం: nothing."}]}
    llm = FakeLLM(routes={SUMMARIZE: [json.dumps(answer)]})
    result = asyncio.run(summarize.summarize(REPORTS, PROFILES, "te", LLMRouter([llm], 5)))
    assert result == {"p_aarav": "విరుద్ధం: Peanuts (22%) పదార్థాల జాబితాలో ఉన్నాయి."}
    prompt = llm.prompts[0]
    assert "Telugu" in prompt and "విరుద్ధం" in prompt and "profile_id p_thatha (Thatha)" in prompt
    reports = summarize.apply(REPORTS, result, "te")
    assert [(r.summary is not None, r.summary_lang) for r in reports] == [(True, "te"), (False, None), (False, None)]


def test_no_llm_means_no_summaries() -> None:
    llm = FakeLLM([ProviderUnavailableError("down")])
    assert asyncio.run(summarize.summarize(REPORTS, PROFILES, "en", LLMRouter([llm], 5))) == {}


def test_summaries_are_never_taken_from_a_local_model() -> None:
    local = FakeLLM(routes={SUMMARIZE: ['{"summaries": []}']}, name="ollama")
    assert asyncio.run(summarize.summarize(REPORTS, PROFILES, "en", LLMRouter([local], 5))) == {}
    assert local.prompts == []
