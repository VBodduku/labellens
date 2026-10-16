from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.quality import add_cropped_edge, assess
from shared.contract import Box, ImageQuality, OcrToken


def prepared(array: np.ndarray) -> PreparedImage:
    image = Image.fromarray(array.astype(np.uint8))
    return PreparedImage("img_0", image.width, image.height, image)


def textured(size: tuple[int, int] = (1200, 900), seed: int = 0) -> np.ndarray:
    """Mid-grey photo-like texture with sharp dark strokes."""
    rng = np.random.default_rng(seed)
    h, w = size
    base = rng.integers(90, 200, size=(h, w), dtype=np.uint8)
    for y in range(40, h - 40, 60):
        cv2.putText(base, "INGREDIENTS SUGAR MILK 22%", (30, y), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 10, 2)
    return np.stack([base] * 3, axis=2)


def test_sharp_photo_is_ok() -> None:
    quality = assess(prepared(textured()))
    assert quality.ok and quality.issues == []
    assert quality.blur_score > 100


def test_blurred_photo_is_blurry() -> None:
    blurred = cv2.GaussianBlur(textured(), (0, 0), sigmaX=6)
    quality = assess(prepared(blurred))
    assert "blurry" in quality.issues and not quality.ok


def test_dark_photo_is_too_dark() -> None:
    quality = assess(prepared(textured() // 5))
    assert "too_dark" in quality.issues
    assert quality.brightness < 60


def test_saturated_patch_is_glare() -> None:
    array = textured()
    array[100:400, 100:500] = 255
    quality = assess(prepared(array))
    assert "glare" in quality.issues
    assert quality.glare_ratio > 0.03


def test_small_photo_is_low_resolution() -> None:
    quality = assess(prepared(textured((500, 400))))
    assert "low_resolution" in quality.issues


def token(i: int, x: float, y: float) -> OcrToken:
    return OcrToken(token_id=f"img_0:t{i}", image_id="img_0", text="w", box=Box(x=x, y=y, w=0.05, h=0.02), confidence=1)


def test_cropped_edge_needs_several_tokens_on_the_border() -> None:
    ok = ImageQuality(ok=True, blur_score=500, glare_ratio=0, brightness=150)
    inside = [token(i, 0.3, 0.1 * i + 0.05) for i in range(8)]
    at_edge = [token(10 + i, 0.96, 0.1 * i + 0.05) for i in range(3)]
    flagged = add_cropped_edge(ok, inside + at_edge)
    assert flagged.issues == ["cropped_edge"] and not flagged.ok
    assert add_cropped_edge(ok, inside + at_edge[:2]) == ok
    assert add_cropped_edge(ok, []) == ok
