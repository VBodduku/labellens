"""Draw the OCR tokens of shared/fixtures/scan_result.json onto a white PNG at their exact boxes.

Gives OCR a test image whose ground truth (text + boxes) is known.
Usage (repo root): python -m backend.scripts.make_test_label [out.png]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.app.config import REPO_ROOT
from shared.contract import OcrToken, ScanResult

FIXTURE = REPO_ROOT / "shared" / "fixtures" / "scan_result.json"
DEFAULT_OUT = REPO_ROOT / ".cache" / "test_label.png"
INK_HEIGHT = 0.8                # fraction of the token box height covered by ink
# Words keep their natural proportions (left-aligned, never wider than the box). Stretching a
# proportional font to the fixture's monospace widths makes OCR drop the spaces between words.
RENDER_SIZE = 64                # glyphs are rendered large, then scaled into each box


def fixture_tokens() -> tuple[list[OcrToken], tuple[int, int]]:
    result = ScanResult.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    info = result.extraction.images[0]
    tokens = [t for t in result.extraction.ocr_tokens if t.image_id == info.image_id]
    return tokens, (info.width, info.height)


def _render_word(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    canvas = Image.new("L", (right - left + 4, bottom - top + 4), 255)
    ImageDraw.Draw(canvas).text((2 - left, 2 - top), text, font=font, fill=0)
    ink = Image.eval(canvas, lambda v: 255 - v).getbbox()
    return canvas.crop(ink) if ink else canvas


def render_label(tokens: list[OcrToken], size: tuple[int, int]) -> Image.Image:
    width, height = size
    page = Image.new("L", size, 255)
    font = ImageFont.load_default(size=RENDER_SIZE)
    for token in tokens:
        text = token.text.replace(" ", " ")
        box_w = max(1, round(token.box.w * width))
        box_h = max(1, round(token.box.h * height))
        ink_h = max(1, round(box_h * INK_HEIGHT))
        glyphs = _render_word(text, font)
        natural_w = round(glyphs.width * ink_h / glyphs.height)
        word = glyphs.resize((min(box_w, natural_w), ink_h), Image.Resampling.LANCZOS)
        x = round(token.box.x * width)
        y = round(token.box.y * height) + (box_h - ink_h) // 2
        page.paste(word, (x, y))
    return page.convert("RGB")


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    tokens, size = fixture_tokens()
    render_label(tokens, size).save(out)
    print(f"wrote {out} ({len(tokens)} tokens, {size[0]}x{size[1]})")


if __name__ == "__main__":
    main(sys.argv)
