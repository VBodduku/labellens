"""Find the label text in a photo, then crop it, turn it upright and enlarge it before OCR and the LLM.

Small, sideways or off-centre print (a label running down an ice-cream cone, a pack on a busy table) is
unreadable at the photo's own scale. RapidOCR's detector finds text lines on a copy scaled to
DETECT_SIDE; the block with the most lines (plus any block with at least KEEP_BLOCK of its lines) becomes
the crop, and mostly vertical lines mean a quarter turn. Blocks are ranked by how many lines they hold, not
by area: a busy background yields big single detections (a striped cloth, a logo), print yields many lines. Which way round reads upright is decided by OCR
confidence. Every box made on the focused view is mapped back to the full photo (`to_full_frame`), so
the evidence overlay still lands on the uploaded image.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, TypeVar

import numpy as np
from PIL import Image
from pydantic import BaseModel

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.ocr import executor, get_engine, ocr_image
from shared.contract import Box, Evidence, OcrToken

FOCUS_VERSION = "focus-v1"      # part of the extraction cache key: a new focus rule re-reads cached photos
DETECT_SIDE = 2000              # the detector misses print a few pixels tall, so small photos are enlarged
FOCUS_SIDE = 2000               # long side of the focused view
MAX_UPSCALE = 4.0
MIN_LINES = 3                   # fewer detected lines: read the photo as it is
CLUSTER_GAP = 0.05              # lines closer than this (x the photo's long side) belong to one block of text
KEEP_BLOCK = 0.2                # other blocks kept down to this share of the main block's line count (a nutrition panel)
MIN_BLOCK_LINES = 2             # a lone detection is a logo or a pattern on the background, not a block of print ...
PRINT_ELONGATION = 6            # ... unless it is a long thin line (a stray "Contains: milk") ...
PRINT_SIZE = (0.6, 1.7)         # ... printed at the main block's size (x its median line thickness)
CROP_BELOW = 0.6                # crop only when the kept text covers less than this share of the photo
PAD = 0.03                      # crop margin, as a share of the photo's sides
VERTICAL = 1.5                  # a line box this much taller than wide holds sideways text
UPRIGHT_CONF = 0.8              # character-weighted OCR confidence that settles the orientation without a second read
FOCUS_TIMEOUT_S = 30.0

logger = logging.getLogger("labellens.focus")
M = TypeVar("M", bound=BaseModel)
_TURN = {1: Image.Transpose.ROTATE_90, 2: Image.Transpose.ROTATE_180, 3: Image.Transpose.ROTATE_270}


@dataclass(frozen=True)
class View:
    """A crop of the photo (normalised corners), then `turns` quarter turns counter-clockwise."""
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 1.0
    y1: float = 1.0
    turns: int = 0

    @property
    def identity(self) -> bool:
        return self == View()


@dataclass(frozen=True)
class Line:
    x0: float                   # normalised axis-aligned bounds of one detected text line
    y0: float
    x1: float
    y1: float
    vertical: bool

    @property
    def area(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)


@dataclass(frozen=True)
class Focused:
    image: PreparedImage        # what OCR and the LLM read; token and LLM boxes are relative to it
    view: View
    tokens: list[OcrToken]


# ------------------------------------------------------------------------------------------------
# Geometry
# ------------------------------------------------------------------------------------------------
def _clamp(value: float) -> float:
    return min(1.0, max(0.0, value))


def _unturn(u: float, v: float, turns: int) -> tuple[float, float]:
    """A point on the turned view -> the same point on the unturned crop."""
    for _ in range(turns % 4):  # one counter-clockwise quarter turn moves crop (x, y) to (y, 1 - x)
        u, v = 1 - v, u
    return u, v


def to_full(box: Box, view: View) -> Box:
    corners = [_unturn(x, y, view.turns) for x, y in ((box.x, box.y), (box.x + box.w, box.y + box.h))]
    xs = [_clamp(view.x0 + x * (view.x1 - view.x0)) for x, _ in corners]
    ys = [_clamp(view.y0 + y * (view.y1 - view.y0)) for _, y in corners]
    return Box(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys))


def render(source: Image.Image, view: View) -> Image.Image:
    w, h = source.size
    crop = source.crop((round(view.x0 * w), round(view.y0 * h), round(view.x1 * w), round(view.y1 * h)))
    if view.turns % 4:
        crop = crop.transpose(_TURN[view.turns % 4])
    scale = min(FOCUS_SIDE / max(crop.size), MAX_UPSCALE)
    size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    return crop.resize(size, Image.Resampling.LANCZOS)


def to_full_frame(model: M, views: dict[str, View]) -> M:
    """Map every Evidence / OcrToken box drawn on a focused view back onto its full photo."""
    if all(v.identity for v in views.values()):
        return model
    remapped: M = _remap(model, views)
    return remapped


def _remap(value: Any, views: dict[str, View]) -> Any:
    if isinstance(value, list):
        items = [_remap(v, views) for v in value]
        return items if any(a is not b for a, b in zip(items, value)) else value
    if not isinstance(value, BaseModel):
        return value
    updates = {}
    for name in type(value).model_fields:
        old = getattr(value, name)
        new = _remap(old, views)
        if new is not old:
            updates[name] = new
    if isinstance(value, (Evidence, OcrToken)) and value.box is not None:
        view = views.get(value.image_id)
        if view is not None and not view.identity:
            updates["box"] = to_full(value.box, view)
    return value.model_copy(update=updates) if updates else value


# ------------------------------------------------------------------------------------------------
# Finding the text
# ------------------------------------------------------------------------------------------------
def detect_lines(image: Image.Image) -> list[Line]:
    scale = DETECT_SIDE / max(image.size)
    sized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.BILINEAR)
    result, _ = get_engine()(np.asarray(sized), use_det=True, use_cls=False, use_rec=False)
    lines = []
    for quad in result or []:
        points = np.asarray(quad, dtype=float).reshape(-1, 2)
        x0, y0 = (float(v) for v in points.min(axis=0))
        x1, y1 = (float(v) for v in points.max(axis=0))
        lines.append(Line(_clamp(x0 / sized.width), _clamp(y0 / sized.height), _clamp(x1 / sized.width),
                          _clamp(y1 / sized.height), vertical=(y1 - y0) > VERTICAL * (x1 - x0)))
    return lines


def _near(a: Line, b: Line, gap_x: float, gap_y: float) -> bool:
    return a.x0 - gap_x <= b.x1 and b.x0 - gap_x <= a.x1 and a.y0 - gap_y <= b.y1 and b.y0 - gap_y <= a.y1


def text_blocks(lines: Sequence[Line], aspect: float) -> list[list[Line]]:
    """Group lines into blocks of text (union-find over lines closer than CLUSTER_GAP), most lines first."""
    gap_x, gap_y = (CLUSTER_GAP, CLUSTER_GAP * aspect) if aspect >= 1 else (CLUSTER_GAP / aspect, CLUSTER_GAP)
    parent = list(range(len(lines)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            if _near(a, lines[j], gap_x, gap_y):
                parent[root(i)] = root(j)
    blocks: dict[int, list[Line]] = {}
    for i, line in enumerate(lines):
        blocks.setdefault(root(i), []).append(line)
    return sorted(blocks.values(), key=lambda block: (-len(block), -sum(line.area for line in block)))


def _sides(line: Line, width: int, height: int) -> tuple[float, float]:
    """(thickness, length) of a line in pixels, whichever way it runs."""
    w, h = (line.x1 - line.x0) * width, (line.y1 - line.y0) * height
    return min(w, h), max(w, h)


def _print_like(line: Line, width: int, height: int, thickness: float) -> bool:
    short, long = _sides(line, width, height)
    return long >= PRINT_ELONGATION * short and PRINT_SIZE[0] * thickness <= short <= PRINT_SIZE[1] * thickness


def candidate_views(lines: Sequence[Line], width: int, height: int) -> list[View]:
    """The views worth reading, likeliest first: the text region, upright then upside down."""
    if len(lines) < MIN_LINES:
        return [View()]
    blocks = text_blocks(lines, width / height)
    least = max(MIN_BLOCK_LINES, KEEP_BLOCK * len(blocks[0]))
    thickness = float(np.median([_sides(line, width, height)[0] for line in blocks[0]]))
    kept = [line for block in blocks
            if len(block) >= least or all(_print_like(line, width, height, thickness) for line in block)
            for line in block]
    if len(kept) < MIN_LINES:
        return [View()]
    x0, y0 = min(line.x0 for line in kept), min(line.y0 for line in kept)
    x1, y1 = max(line.x1 for line in kept), max(line.y1 for line in kept)
    region = (_clamp(x0 - PAD), _clamp(y0 - PAD), _clamp(x1 + PAD), _clamp(y1 + PAD))
    if (region[2] - region[0]) * (region[3] - region[1]) >= CROP_BELOW:
        region = (0.0, 0.0, 1.0, 1.0)
    sideways = sum(line.area for line in kept if line.vertical) > sum(line.area for line in kept) / 2
    turns = (1, 3) if sideways else (0, 2)
    return [View(*region, turns=t) for t in turns]


# ------------------------------------------------------------------------------------------------
# Reading
# ------------------------------------------------------------------------------------------------
def _confidence(tokens: Sequence[OcrToken]) -> float:
    chars = sum(len(t.text) for t in tokens)
    return sum(t.confidence * len(t.text) for t in tokens) / chars if chars else 0.0


def _score(tokens: Sequence[OcrToken]) -> float:
    return sum(t.confidence * len(t.text) for t in tokens)


def focus_and_read(image: PreparedImage) -> Focused:
    """Blocking: detect the text, then OCR each candidate view until one reads confidently; keep the best."""
    source = image.source or image.ocr_image
    first, *others = candidate_views(detect_lines(source), source.width, source.height)
    best = _read(image, source, first)
    for view in others:
        if _confidence(best.tokens) >= UPRIGHT_CONF:
            break
        read = _read(image, source, view)
        if _score(read.tokens) > _score(best.tokens):
            best = read
    return best


def _read(image: PreparedImage, source: Image.Image, view: View) -> Focused:
    seen = image if view.identity else replace(image, ocr_image=render(source, view), source=None)
    return Focused(seen, view, ocr_image(seen.ocr_image, image.image_id))


async def read_panel(image: PreparedImage, timeout_s: float = FOCUS_TIMEOUT_S) -> Focused:
    """Focus + OCR in the thread pool; a stuck run reads nothing rather than blocking the scan."""
    loop = asyncio.get_running_loop()
    try:
        focused = await asyncio.wait_for(loop.run_in_executor(executor(), focus_and_read, image), timeout_s)
    except TimeoutError:
        logger.warning("focus timed out", extra={"fields": {"image_id": image.image_id, "timeout_s": timeout_s}})
        return Focused(image, View(), [])
    return focused
