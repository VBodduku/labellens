from __future__ import annotations

from PIL import Image

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.structure import build_prompt, cap_tokens, format_tokens, llm_image
from backend.tests.fakes import token


def test_token_list_is_grouped_per_image_with_full_ids() -> None:
    tokens = [token(0, "Sugar,", 0.1, 0.1), token(1, "Milk", 0.2, 0.1), token(0, "Salt", 0.1, 0.1, image_id="img_1")]
    text = format_tokens(tokens, ["img_0", "img_1", "img_2"], cap=100)
    assert text == "## img_0\nimg_0:t0|Sugar,\nimg_0:t1|Milk\n\n## img_1\nimg_1:t0|Salt\n\n## img_2\n(no OCR text)"


def test_cap_drops_low_confidence_first_then_least_confident_keeping_order() -> None:
    tokens = [token(n, f"w{n}", 0.1, 0.1, confidence=c) for n, c in enumerate([0.9, 0.2, 0.5, 0.95, 0.1, 0.6])]
    kept = cap_tokens(tokens, 3)
    assert [t.text for t in kept] == ["w0", "w3", "w5"]
    assert cap_tokens(tokens, 10) == tokens


def test_prompt_contains_rules_images_and_tokens() -> None:
    image = PreparedImage("img_0", 100, 100, Image.new("RGB", (100, 100), "white"))
    prompt = build_prompt([image], ["back"], [token(0, "Sugar,", 0.1, 0.1)], cap=10)
    assert "- img_0: back panel" in prompt
    assert "img_0:t0|Sugar," in prompt
    assert "Transcribe, never infer" in prompt
    assert "{token_list}" not in prompt and "{image_list}" not in prompt


def test_llm_image_is_jpeg_capped_at_1600() -> None:
    image = PreparedImage("img_0", 2000, 1000, Image.new("RGB", (2000, 1000), "white"))
    part = llm_image(image)
    assert part.mime_type == "image/jpeg" and part.data[:2] == b"\xff\xd8"
