"""RapidOCR wrapper: line detections -> word-level OcrTokens with normalised boxes in reading order."""
from __future__ import annotations

import asyncio
import statistics
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from PIL import Image
from rapidocr_onnxruntime import RapidOCR

from backend.app.pipeline.images import PreparedImage
from shared.contract import Box, OcrToken

ROW_TOLERANCE = 0.5             # lines whose centres differ by < this x median line height share a row

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ocr")


@dataclass(frozen=True)
class OcrLine:
    x0: float                   # axis-aligned pixel bbox of the detected quadrilateral
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def centre_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class WordBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float


@lru_cache(maxsize=1)
def get_engine() -> RapidOCR:
    return RapidOCR()


def parse_raw(result: Sequence[Sequence[Any]] | None) -> list[OcrLine]:
    """RapidOCR returns [[4 points], text, score] per detected line, or None for nothing."""
    lines: list[OcrLine] = []
    for points, text, score in result or []:
        if not str(text).strip():
            continue
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        lines.append(OcrLine(min(xs), min(ys), max(xs), max(ys), str(text), float(score)))
    return lines


def order_lines(lines: list[OcrLine]) -> list[OcrLine]:
    """Top-to-bottom rows (tolerant of slight rotation), left-to-right inside a row."""
    if not lines:
        return []
    tolerance = ROW_TOLERANCE * statistics.median(line.height for line in lines)
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda l: l.centre_y):
        row = rows[-1] if rows else None
        if row is not None and abs(line.centre_y - statistics.fmean(l.centre_y for l in row)) < tolerance:
            row.append(line)
        else:
            rows.append([line])
    return [line for row in rows for line in sorted(row, key=lambda l: l.x0)]


def split_line(line: OcrLine) -> list[WordBox]:
    """Split a line into words, giving each a share of the line width proportional to its characters."""
    text = line.text
    width = line.x1 - line.x0
    words: list[WordBox] = []
    position = 0
    for word in text.split():
        start = text.index(word, position)
        end = start + len(word)
        position = end
        words.append(WordBox(
            text=word,
            x0=line.x0 + width * start / len(text),
            y0=line.y0,
            x1=line.x0 + width * end / len(text),
            y1=line.y1,
            score=line.score,
        ))
    return words


def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def normalised_box(word: WordBox, img_w: int, img_h: int) -> Box:
    x0, x1 = _clamp(word.x0 / img_w), _clamp(word.x1 / img_w)
    y0, y1 = _clamp(word.y0 / img_h), _clamp(word.y1 / img_h)
    return Box(x=round(x0, 4), y=round(y0, 4), w=round(x1 - x0, 4), h=round(y1 - y0, 4))


def tokens_from_lines(lines: list[OcrLine], image_id: str, img_w: int, img_h: int) -> list[OcrToken]:
    tokens: list[OcrToken] = []
    for line in order_lines(lines):
        for word in split_line(line):
            tokens.append(OcrToken(
                token_id=f"{image_id}:t{len(tokens)}",
                image_id=image_id,
                text=word.text,
                box=normalised_box(word, img_w, img_h),
                confidence=round(word.score, 4),
            ))
    return tokens


def ocr_image(image: Image.Image, image_id: str) -> list[OcrToken]:
    """Blocking OCR of one RGB image. Prefer run_ocr from async code."""
    result, _ = get_engine()(image)
    return tokens_from_lines(parse_raw(result), image_id, image.width, image.height)


async def run_ocr(image: PreparedImage) -> list[OcrToken]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, ocr_image, image.ocr_image, image.image_id)
