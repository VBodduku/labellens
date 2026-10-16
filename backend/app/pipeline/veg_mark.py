"""Pixel check of the green FSSAI veg mark the model located (a green square outline around a green dot).

OCR cannot read a symbol, so the model's box is the only evidence for the mark, and in acceptance runs the
model gave a box for a green mark on a pack that has none. A green mark loosens verdicts (it resolves
slaughter-derived ambiguity, master spec §9), so it is kept only when the photo is actually green in and
around that box; otherwise it counts as unclear. A brown/red mark is the stricter reading and is never
downgraded here.
"""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PIL import Image

from backend.app.pipeline.images import PreparedImage
from shared.contract import Box, LabelExtraction, VegMark

PAD = 0.5                  # the model's box grows by half its size on every side: its boxes are approximate
MIN_PIXELS = 12            # never judge a region smaller than this many pixels per side
MIN_GREEN = 0.01           # share of clearly green pixels: a real mark scored 0.10 (0.012 with a box 3x too big),
                           # the purple Bingo back label, which has no mark, 0.000 everywhere
HUE_GREEN = (42, 120)      # PIL hue 0..255: roughly 60°..170°, yellow-green to teal
MIN_SATURATION = 90
MIN_VALUE = 60


def green_ratio(image: Image.Image, box: Box) -> float:
    """Share of saturated green pixels in the padded box (0 when the region is degenerate)."""
    w, h = image.size
    x0 = max(0, int((box.x - box.w * PAD) * w))
    y0 = max(0, int((box.y - box.h * PAD) * h))
    x1 = min(w, int((box.x + box.w * (1 + PAD)) * w) + 1)
    y1 = min(h, int((box.y + box.h * (1 + PAD)) * h) + 1)
    if x1 - x0 < MIN_PIXELS or y1 - y0 < MIN_PIXELS:
        return 0.0
    hsv = np.asarray(image.crop((x0, y0, x1, y1)).convert("HSV"))
    hue, saturation, value = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    green = (hue >= HUE_GREEN[0]) & (hue <= HUE_GREEN[1]) & (saturation >= MIN_SATURATION) & (value >= MIN_VALUE)
    return float(green.mean())


def checked_veg_mark(extraction: LabelExtraction, images: Sequence[PreparedImage]) -> LabelExtraction:
    """Boxes must already be on the full photo (after focus.to_full_frame)."""
    mark = extraction.veg_mark
    evidence = mark.evidence
    if mark.value != "veg" or evidence is None or evidence.box is None:
        return extraction
    image = next((i for i in images if i.image_id == evidence.image_id), None)
    if image is not None and green_ratio(image.ocr_image, evidence.box) >= MIN_GREEN:
        return extraction
    return extraction.model_copy(update={"veg_mark": VegMark(value="unclear")})
