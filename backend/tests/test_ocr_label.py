"""Real RapidOCR on the rendered fixture label: words found where the fixture says they are."""
from __future__ import annotations

import asyncio
import re
import time

from PIL import Image
from rapidfuzz import fuzz

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.ocr import ocr_image, run_ocr
from backend.scripts.make_test_label import fixture_tokens
from shared.contract import Box, OcrToken

MIN_FOUND = 0.90
MIN_IOU = 0.3
MIN_TEXT_SCORE = 80


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a.x + a.w, b.x + b.w) - max(a.x, b.x))
    iy = max(0.0, min(a.y + a.h, b.y + b.h) - max(a.y, b.y))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union else 0.0


def union_box(boxes: list[Box]) -> Box:
    x0, y0 = min(b.x for b in boxes), min(b.y for b in boxes)
    x1, y1 = max(b.x + b.w for b in boxes), max(b.y + b.h for b in boxes)
    return Box(x=x0, y=y0, w=x1 - x0, h=y1 - y0)


def normalise(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def found(expected: OcrToken, ocr_tokens: list[OcrToken]) -> bool:
    e = expected.box
    inside = [
        t for t in ocr_tokens
        if e.x <= t.box.x + t.box.w / 2 <= e.x + e.w and e.y <= t.box.y + t.box.h / 2 <= e.y + e.h
    ]
    if not inside:
        return False
    text = "".join(t.text for t in inside)
    return (fuzz.ratio(normalise(text), normalise(expected.text)) >= MIN_TEXT_SCORE
            and iou(union_box([t.box for t in inside]), e) >= MIN_IOU)


def test_ocr_finds_fixture_words_at_fixture_boxes(label_image: Image.Image) -> None:
    expected, _ = fixture_tokens()
    started = time.perf_counter()
    tokens = ocr_image(label_image, "img_0")
    elapsed_ms = (time.perf_counter() - started) * 1000

    missed = [t.text for t in expected if not found(t, tokens)]
    ratio = 1 - len(missed) / len(expected)
    print(f"OCR {elapsed_ms:.0f} ms, {len(tokens)} tokens, found {ratio:.1%}, missed {missed}")
    assert ratio >= MIN_FOUND
    assert [t.token_id for t in tokens] == [f"img_0:t{i}" for i in range(len(tokens))]


def test_run_ocr_uses_thread_pool_and_image_id(label_image: Image.Image) -> None:
    crop = label_image.crop((0, 0, 1000, 200))
    prepared = PreparedImage("img_2", crop.width, crop.height, crop)
    tokens = asyncio.run(run_ocr(prepared))
    assert [t.text for t in tokens[:3]] == ["NUVO", "CHOCO", "NUT"]
    assert all(t.token_id.startswith("img_2:t") for t in tokens)
