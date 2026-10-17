from __future__ import annotations

from PIL import Image

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.structure import build_prompt, cap_tokens, citations_for, format_tokens, llm_image
from backend.tests.fakes import recorded, token


def test_token_list_is_grouped_per_image_with_full_ids() -> None:
    tokens = [token(0, "Sugar,", 0.1, 0.1), token(1, "Milk", 0.2, 0.1), token(0, "Salt", 0.1, 0.1, image_id="img_1")]
    text = format_tokens(tokens, ["img_0", "img_1", "img_2"], cap=100)
    assert text == "## img_0\n0|Sugar,\n1|Milk\n\n## img_1\n0|Salt\n\n## img_2\n(no OCR text)"
    assert citations_for(tokens, ["img_0", "img_1"], cap=100) == {"img_0": ["img_0:t0", "img_0:t1"], "img_1": ["img_1:t0"]}


def test_cap_drops_low_confidence_first_then_least_confident_keeping_order() -> None:
    tokens = [token(n, f"w{n}", 0.1, 0.1, confidence=c) for n, c in enumerate([0.9, 0.2, 0.5, 0.95, 0.1, 0.6])]
    kept = cap_tokens(tokens, 3)
    assert [t.text for t in kept] == ["w0", "w3", "w5"]
    assert cap_tokens(tokens, 10) == tokens


def test_prompt_contains_rules_images_and_tokens() -> None:
    image = PreparedImage("img_0", 100, 100, Image.new("RGB", (100, 100), "white"))
    prompt = build_prompt([image], ["back"], [token(0, "Sugar,", 0.1, 0.1)], cap=10)
    assert "- img_0: back panel" in prompt
    assert "0|Sugar," in prompt
    assert "Transcribe, never infer" in prompt
    assert "{token_list}" not in prompt and "{image_list}" not in prompt


def test_llm_image_is_jpeg_capped_at_1600() -> None:
    image = PreparedImage("img_0", 2000, 1000, Image.new("RGB", (2000, 1000), "white"))
    part = llm_image(image)
    assert part.mime_type == "image/jpeg" and part.data[:2] == b"\xff\xd8"


def test_an_empty_reading_of_a_photo_full_of_text_is_rejected() -> None:
    from backend.app.pipeline.llm_schema import LLMExtraction
    from backend.app.pipeline.structure import empty_reading

    section = {"presence": "not_found", "complete": False}
    empty = LLMExtraction.model_validate({"panels": [{"image_id": "img_0", "ingredients_section": section,
                                                       "allergen_section": section, "nutrition_section": section,
                                                       "veg_mark": {"value": "not_found"}}]})
    assert empty_reading(empty, 180) is not None and "180 words" in (empty_reading(empty, 180) or "")
    assert empty_reading(empty, 5) is None                       # a photo with almost no text may really be empty
    full = LLMExtraction.model_validate_json(recorded("ollama_test_label.json"))
    assert empty_reading(full, 180) is None
