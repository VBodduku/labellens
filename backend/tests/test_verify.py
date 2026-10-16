"""Self-verification loop (spec §4.6)."""
from __future__ import annotations

import asyncio
import json

import pytest
from PIL import Image

from backend.tests import fixture_data as fixtures
from backend.app.llm.base import RateLimitedError
from backend.app.llm.router import LLMRouter
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.verify import (
    find_triggers,
    map_tokens,
    merge_unknowns,
    padded_crop,
    pending_unknowns,
    verify,
)
from backend.scripts.make_test_label import fixture_tokens, render_label
from backend.tests.fakes import REREAD, FakeLLM, token
from shared.contract import Box, Evidence, LabelExtraction, Profile, UnknownItem

PROFILES = [Profile.model_validate(p)
            for p in json.loads((fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))]


def label_image(readable_sodium: bool) -> PreparedImage:
    """The fixture label; optionally with the smudged sodium values printed clearly."""
    tokens, size = fixture_tokens()
    if readable_sodium:
        tokens = [t.model_copy(update={"text": {"1?5": "175", "??": "70"}.get(t.text, t.text)}) for t in tokens]
    image = render_label(tokens, size)
    return PreparedImage("img_0", image.width, image.height, image)


def extraction() -> LabelExtraction:
    return fixtures.scan_result().extraction.model_copy(update={"meta": fixtures.scan_result().extraction.meta
                                                                 .model_copy(update={"provider": "gemini", "retries": [],
                                                                                     "attempts": 1})})


def reread_sodium(text: str) -> str:
    return json.dumps({"product_name": None, "languages": [], "panels": [{
        "image_id": "img_0", "panel": "back", "ingredients": [],
        "ingredients_section": {"presence": "not_found", "complete": False, "issues": [], "unreadable_token_ids": [],
                                "unreadable_boxes": []},
        "allergen_statements": [],
        "allergen_section": {"presence": "not_found", "complete": False, "issues": [], "unreadable_token_ids": [],
                             "unreadable_boxes": []},
        "nutrition": {"serving_size": None, "serving_unit": None, "servings_per_pack": None, "pack_size": None,
                      "pack_unit": None, "rows": [{"key": "sodium_mg", "label": "Sodium", "values": [
                          {"basis": "per_100g", "amount": 175, "unit": "mg", "text": text, "token_ids": [],
                           "readability": "clear", "box_2d": None}]}]},
        "nutrition_section": {"presence": "found", "complete": True, "issues": [], "unreadable_token_ids": [],
                              "unreadable_boxes": []},
        "veg_mark": {"value": "not_found", "box_2d": None}, "claims": []}]})


def run(e: LabelExtraction, image: PreparedImage, llm: FakeLLM, budget_s: float = 25) -> LabelExtraction:
    return asyncio.run(verify(e, [image], PROFILES, LLMRouter([llm], 10), budget_s))


def test_fixture_triggers_on_unreadable_sodium_needed_by_thatha() -> None:
    [trigger] = find_triggers(extraction(), PROFILES)
    assert trigger.reason == "nutrition_value_unreadable:sodium_mg"
    assert trigger.section == "nutrition" and trigger.box.y == pytest.approx(0.8174)


def test_reread_that_finds_the_value_on_the_photo_is_accepted() -> None:
    llm = FakeLLM(routes={REREAD: [reread_sodium("175")]})
    result = run(extraction(), label_image(readable_sodium=True), llm)
    [retry] = result.meta.retries
    assert (retry.reason, retry.action, retry.outcome) == ("nutrition_value_unreadable:sodium_mg",
                                                            "reread_region:img_0", "resolved")
    sodium = next(r for r in result.nutrition.rows if r.key == "sodium_mg")  # type: ignore[union-attr]
    value = next(v for v in sodium.values if v.basis == "per_100g")
    assert value.amount == 175 and value.evidence is not None and value.evidence.status == "verified"
    assert any(t.token_id.startswith("img_0:r1t") for t in result.ocr_tokens)
    assert result.meta.attempts == 2
    assert pending_unknowns(result, PROFILES) == []
    assert "Focused re-read" in llm.prompts[0] and "the sodium_mg row" in llm.prompts[0]
    assert llm.images[0][0].mime_type == "image/jpeg"


def test_reread_with_a_guessed_value_is_rejected_and_becomes_a_retake_unknown() -> None:
    llm = FakeLLM(routes={REREAD: [reread_sodium("175 mg")]})       # photo still says "1?5"
    result = run(extraction(), label_image(readable_sodium=False), llm)
    assert [r.outcome for r in result.meta.retries] == ["unchanged"]
    [unknown] = pending_unknowns(result, PROFILES)
    assert unknown.message_key == "unknown.retake_region" and unknown.section == "nutrition"
    assert unknown.region is not None and unknown.region.box is not None


def test_no_budget_or_rate_limit_skips_without_calling_the_llm() -> None:
    llm = FakeLLM(routes={REREAD: [reread_sodium("175")]})
    assert [r.outcome for r in run(extraction(), label_image(True), llm, budget_s=1).meta.retries] == ["skipped_budget"]
    limited = FakeLLM([RateLimitedError(60)])
    router = LLMRouter([limited], 10)
    router.report_rate_limit(limited.label, 60)
    result = asyncio.run(verify(extraction(), [label_image(True)], PROFILES, router))
    assert [r.outcome for r in result.meta.retries] == ["skipped_rate_limit"]
    assert llm.prompts == [] and limited.prompts == []


def test_ocr_only_is_not_verified() -> None:
    e = extraction()
    e = e.model_copy(update={"meta": e.meta.model_copy(update={"provider": "ocr_only"})})
    assert run(e, label_image(True), FakeLLM()).meta.retries == []


def test_truncated_ingredients_ask_for_retake_without_llm() -> None:
    e = extraction()
    section = e.ingredients_section.model_copy(update={"complete": False, "issues": ["truncated_at_image_edge"]})
    e = e.model_copy(update={"ingredients_section": section})
    llm = FakeLLM()
    result = run(e, label_image(False), llm, budget_s=1)
    assert [(r.reason, r.action, r.outcome) for r in result.meta.retries][0] == (
        "ingredients_truncated", "ask_user_retake", "unresolved")
    truncated = [u for u in pending_unknowns(result, PROFILES) if u.message_key == "unknown.ingredients_truncated"]
    assert truncated and truncated[0].region is not None and truncated[0].section == "ingredients"


def test_triggers_in_spec_order_and_at_most_two_rereads() -> None:
    e = extraction()
    nutrition = e.nutrition.model_copy(deep=True)  # type: ignore[union-attr]
    energy = next(r for r in nutrition.rows if r.key == "energy_kcal")
    energy.values[0].amount = 950.0                                   # inconsistent with the macros
    unreadable = Evidence(image_id="img_0", text="", box=Box(x=0.06, y=0.30, w=0.3, h=0.02), status="verified")
    section = e.ingredients_section.model_copy(update={"complete": False, "unreadable_regions": [unreadable]})
    unverified = [i.model_copy(update={"evidence": [Evidence(image_id="img_0", text=i.name, status="unverified")]})
                  for i in e.ingredients]
    e = e.model_copy(update={"nutrition": nutrition, "ingredients_section": section, "ingredients": unverified})

    reasons = [t.reason for t in find_triggers(e, PROFILES)]
    assert reasons == ["nutrition_inconsistent", "ingredients_unreadable",
                       "nutrition_value_unreadable:sodium_mg", "evidence_unverified"]
    llm = FakeLLM(routes={REREAD: [reread_sodium("999 mg")]})
    result = run(e, label_image(False), llm)
    assert [r.outcome for r in result.meta.retries] == ["unchanged", "unchanged", "skipped_budget", "skipped_budget"]
    assert len(llm.calls(REREAD)) == 2


def test_crop_is_padded_upscaled_and_tokens_map_back() -> None:
    image = PreparedImage("img_0", 1000, 1000, Image.new("RGB", (1000, 1000), "white"))
    crop = padded_crop(image, Box(x=0.5, y=0.5, w=0.2, h=0.1))
    assert (crop.x0, crop.y0, crop.width, crop.height) == (484, 492, 233, 117)
    assert crop.image.size == (466, 234)
    [mapped] = map_tokens([token(0, "Sodium", 0.5, 0.5, w=0.5, h=0.5)], crop, image, round_no=2)
    assert mapped.token_id == "img_0:r2t0"
    assert (mapped.box.x, mapped.box.y) == (pytest.approx(0.6005, abs=1e-3), pytest.approx(0.5505, abs=1e-3))
    assert mapped.box.w == pytest.approx(0.1165, abs=1e-3)


def test_pipeline_unknowns_with_regions_replace_engine_duplicates() -> None:
    region = Evidence(image_id="img_0", text="", box=Box(x=0, y=0, w=0.1, h=0.1), status="approximate")
    engine = [UnknownItem(section="ingredients", message_key="unknown.ingredients_truncated"),
              UnknownItem(section="veg_mark", message_key="unknown.veg_mark_unclear")]
    pipeline = [UnknownItem(section="ingredients", message_key="unknown.ingredients_truncated", region=region)]
    merged = merge_unknowns(engine, pipeline)
    assert [(u.message_key, u.region is not None) for u in merged] == [
        ("unknown.ingredients_truncated", True), ("unknown.veg_mark_unclear", False)]
