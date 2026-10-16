"""End-to-end scan pipeline with a FakeLLM: grounding, fallback, caching, parallel OCR."""
from __future__ import annotations

import asyncio
import io
import json

import pytest
from PIL import Image

from backend.app.cache import ExtractionCache
from backend.app.errors import ApiError
from backend.tests.fixture_data import FIXTURES_DIR
from backend.app.llm.base import ProviderUnavailableError, RateLimitedError
from backend.app.pipeline import orchestrator
from backend.app.pipeline.align import union_box
from backend.app.pipeline.focus import Focused, View
from backend.app.pipeline.images import decode_upload
from backend.app.pipeline.orchestrator import ScanInput, run_scan
from backend.scripts.make_test_label import fixture_tokens
from backend.tests.fakes import STRUCTURE, FakeLLM, recorded, router_with, scan_llm, token
from backend.tests.test_ocr_label import iou
from shared.contract import Profile, ScanResult

PROFILES = [Profile.model_validate(p)
            for p in json.loads((FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))]


def scan_input(png: bytes, count: int = 1) -> ScanInput:
    return ScanInput(
        images=[decode_upload(png, f"img_{n}") for n in range(count)], raw=[png] * count,
        hints=["back"], profiles=PROFILES, lang="en",
    )


def scan(png: bytes, llm: FakeLLM, cache: ExtractionCache, count: int = 1) -> ScanResult:
    return asyncio.run(run_scan(scan_input(png, count), router_with(llm), cache))


def test_evidence_boxes_land_on_the_printed_words(label_png: bytes, cache: ExtractionCache) -> None:
    result = scan(label_png, scan_llm(recorded("ollama_test_label.json")), cache)
    extraction = result.extraction
    assert (extraction.meta.provider, extraction.meta.model, extraction.meta.cache_hit) == ("ollama", "gemma3:4b", False)
    expected = {t.text: t.box for t in fixture_tokens()[0]}
    printed = union_box([expected["Peanuts"], expected["(22%),"]])
    peanuts = next(i for i in extraction.ingredients if i.name.startswith("Peanuts"))
    [evidence] = peanuts.evidence
    assert evidence.status == "verified" and evidence.box is not None
    assert iou(evidence.box, printed) >= 0.3
    assert all(e.box is not None for i in extraction.ingredients for e in i.evidence if e.status == "verified")
    assert extraction.images[0].quality.blur_score > 0
    assert len(result.reports) == 3


def test_all_providers_down_gives_honest_ocr_only_result(label_png: bytes, cache: ExtractionCache) -> None:
    llm = FakeLLM([ProviderUnavailableError("down")])
    result = scan(label_png, llm, cache)
    extraction = result.extraction
    assert extraction.meta.provider == "ocr_only"
    assert len(extraction.ingredients) == 11
    assert not extraction.ingredients_section.complete
    assert all(r.state != "not_listed" for report in result.reports for r in report.results)
    assert not list(cache.directory.glob("*.json"))            # degraded results are not cached


def test_rate_limited_everywhere_still_answers(label_png: bytes, cache: ExtractionCache) -> None:
    result = scan(label_png, FakeLLM([RateLimitedError(30)]), cache)
    assert result.extraction.meta.provider == "ocr_only"


def test_second_scan_is_a_cache_hit_without_llm_call(label_png: bytes, cache: ExtractionCache) -> None:
    llm = scan_llm(recorded("ollama_test_label.json"))
    first = scan(label_png, llm, cache)
    second = scan(label_png, llm, cache)
    assert len(llm.calls(STRUCTURE)) == 1
    assert second.extraction.meta.cache_hit is True
    assert second.scan_id != first.scan_id
    assert second.extraction.ingredients == first.extraction.ingredients


def test_panels_run_ocr_in_parallel(label_png: bytes, cache: ExtractionCache, monkeypatch: pytest.MonkeyPatch) -> None:
    active, peak = 0, 0

    async def slow_ocr(image):  # type: ignore[no-untyped-def]
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.05)
        active -= 1
        return Focused(image, View(), [token(0, "Sugar", 0.1, 0.1, image_id=image.image_id)])

    monkeypatch.setattr(orchestrator, "read_panel", slow_ocr)
    scan(label_png, scan_llm(recorded("ollama_test_label.json")), cache, count=3)
    assert peak == 3


def test_blank_photo_is_rejected(cache: ExtractionCache) -> None:
    buffer = io.BytesIO()
    Image.new("RGB", (800, 800), (128, 128, 128)).save(buffer, format="PNG")
    with pytest.raises(ApiError) as info:
        scan(buffer.getvalue(), scan_llm(recorded("ollama_test_label.json")), cache)
    assert info.value.error_code == "BAD_IMAGE"


def test_unresolved_terms_are_interpreted_and_evaluated_again(
    label_png: bytes, cache: ExtractionCache, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app import engine_adapter
    from backend.tests.fakes import INTERPRET
    from shared.engine_interface import UnresolvedTerm

    real_evaluate = engine_adapter.evaluate
    calls: list[object] = []

    def evaluate(extraction, profiles, interpretations=None):  # type: ignore[no-untyped-def]
        calls.append(interpretations)
        output = real_evaluate(extraction, profiles, interpretations)
        return output.model_copy(update={"unresolved_terms": [UnresolvedTerm(ingredient_id="ing_6", term="Zorbex")]})

    monkeypatch.setattr(orchestrator.engine_adapter, "evaluate", evaluate)
    answer = {"interpretations": [{"term": "Zorbex", "categories": ["milk"], "origin": "varies",
                                   "confidence": 0.6, "rationale": "May be dairy based."}]}
    llm = scan_llm(recorded("ollama_test_label.json"), interpret=[json.dumps(answer)])
    scan(label_png, llm, cache)
    assert calls[0] is None
    assert list(calls[1]) == ["Zorbex"] and calls[1]["Zorbex"].categories == ["milk"]  # type: ignore[index]


def test_recorded_gemini_reading_is_fully_grounded_and_gives_all_four_states(
    label_png: bytes, cache: ExtractionCache,
) -> None:
    """A real Gemini response for the test label, through the real pipeline and engine."""
    llm = scan_llm(recorded("gemini_test_label.json"), name="gemini", model="gemini-flash-lite-latest")
    result = scan(label_png, llm, cache)
    e = result.extraction
    assert len(e.ingredients) == 11
    assert all(i.evidence[0].status == "verified" for i in e.ingredients)
    assert e.ingredients_section.complete is True
    sodium = next(r for r in e.nutrition.rows if r.key == "sodium_mg")  # type: ignore[union-attr]
    assert all(v.amount is None for v in sodium.values)
    assert e.nutrition_section.complete is False                          # model said complete; guard says no
    states = {r.state for report in result.reports for r in report.results}
    assert states == {"conflict", "possible", "not_listed", "unknown"}
    overall = {r.profile_id: r.overall for r in result.reports}
    assert overall["p_aarav"] == "conflict" and overall["p_thatha"] == "conflict"
    assert any(u.message_key == "unknown.retake_region" and u.region is not None for u in result.unknowns)


def test_the_ai_misreading_a_printed_number_is_shown_and_not_used(label_png: bytes, cache: ExtractionCache) -> None:
    """Test 3 of docs/TEST_RESULTS.md: real OCR of the demo label; the model reads Total Sugars as 33.0 g where
    the photo prints 38.0 g. Neither number decides a verdict until the user checks the pack."""
    answer = json.loads(recorded("gemini_test_label.json"))
    sugars = next(r for r in answer["panels"][0]["nutrition"]["rows"] if r["key"] == "total_sugars_g")
    sugars["values"][0]["amount"] = 33.0
    result = scan(label_png, scan_llm(json.dumps(answer), name="gemini", model="gemini-test"), cache)
    [contradiction] = [c for c in result.contradictions if c.kind == "ai_vs_print"]
    assert contradiction.message_params == {"nutrient": "total_sugars_g", "ai_value": 33.0, "value": 38.0}
    value = next(r for r in result.extraction.nutrition.rows if r.key == "total_sugars_g").values[0]  # type: ignore[union-attr]
    assert (value.amount, value.readability) == (38.0, "partial")       # the printed number, held back
    thatha_sugar = next(r for p in result.reports if p.profile_id == "p_thatha" for r in p.results
                        if r.restriction_id == "r_thatha_sugar")
    assert thatha_sugar.message_params.get("value") != 33.0              # the AI's number never decides it


def test_an_allergen_statement_the_ai_left_out_is_read_from_the_ocr_words(label_png: bytes, cache: ExtractionCache) -> None:
    answer = json.loads(recorded("gemini_test_label.json"))
    answer["panels"][0]["allergen_statements"] = []
    result = scan(label_png, scan_llm(json.dumps(answer), name="gemini", model="gemini-test"), cache)
    statements = {(s.type, tuple(s.items)) for s in result.extraction.allergen_statements}
    assert ("contains", ("PEANUT", "MILK", "WHEAT", "SOY")) in statements
    assert all(e.status == "verified" for s in result.extraction.allergen_statements for e in s.evidence)
    assert "statements_from_ocr" in result.extraction.allergen_section.issues
    sesame = next(r for p in result.reports for r in p.results if r.restriction_id == "r_lakshmi_sesame")
    assert sesame.state != "conflict"
