"""Time decode + quality + OCR on one photo and print the first tokens.

Usage (repo root): python -m backend.scripts.ocr_probe path/to/photo.jpg
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from backend.app.pipeline import ocr, quality
from backend.app.pipeline.images import decode_upload

SHOW_TOKENS = 30


def main(argv: list[str]) -> None:
    if len(argv) != 2:
        raise SystemExit("usage: python -m backend.scripts.ocr_probe <photo>")
    data = Path(argv[1]).read_bytes()

    started = time.perf_counter()
    ocr.get_engine()
    init_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    image = decode_upload(data, "img_0")
    decode_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    q = quality.assess(image)
    quality_ms = (time.perf_counter() - started) * 1000

    started = time.perf_counter()
    tokens = ocr.ocr_image(image.ocr_image, image.image_id)
    ocr_ms = (time.perf_counter() - started) * 1000
    q = quality.add_cropped_edge(q, tokens)

    print(f"image: {image.original_width}x{image.original_height} -> {image.width}x{image.height}")
    print(f"quality: {q.model_dump()}")
    print(f"timings ms: init={init_ms:.0f} decode={decode_ms:.0f} quality={quality_ms:.0f} ocr={ocr_ms:.0f}")
    print(f"tokens: {len(tokens)}")
    for token in tokens[:SHOW_TOKENS]:
        b = token.box
        print(f"  {token.token_id:<12} {token.confidence:.2f}  ({b.x:.3f},{b.y:.3f},{b.w:.3f},{b.h:.3f})  {token.text}")


if __name__ == "__main__":
    main(sys.argv)
