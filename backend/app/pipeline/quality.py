"""Server-side photo quality heuristics (blur, glare, brightness, resolution, cropped edge)."""
from __future__ import annotations

import cv2
import numpy as np

from backend.app.pipeline.images import PreparedImage, resized
from shared.contract import ImageQuality, OcrToken, QualityIssue

ANALYSIS_MAX_SIDE = 1024
BLUR_THRESHOLD = 100.0          # Laplacian variance; below this the photo is called blurry
GLARE_PIXEL_MIN = 250           # every channel at least this bright -> blown-out highlight
GLARE_RATIO_MAX = 0.03
DARK_BRIGHTNESS_MAX = 60.0
MIN_SHORT_SIDE = 600
EDGE_MARGIN = 0.01
EDGE_MIN_TOKENS = 3
EDGE_MIN_FRACTION = 0.10


def assess(image: PreparedImage) -> ImageQuality:
    rgb = np.asarray(resized(image.ocr_image, ANALYSIS_MAX_SIDE))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    glare_ratio = float(np.mean(rgb.min(axis=2) >= GLARE_PIXEL_MIN))
    brightness = float(gray.mean())

    issues: list[QualityIssue] = []
    if blur_score < BLUR_THRESHOLD:
        issues.append("blurry")
    if glare_ratio > GLARE_RATIO_MAX:
        issues.append("glare")
    if brightness < DARK_BRIGHTNESS_MAX:
        issues.append("too_dark")
    if min(image.original_width, image.original_height) < MIN_SHORT_SIDE:
        issues.append("low_resolution")
    return ImageQuality(
        ok=not issues,
        blur_score=round(blur_score, 1),
        glare_ratio=round(glare_ratio, 4),
        brightness=round(brightness, 1),
        issues=issues,
    )


def _touches_edge(token: OcrToken) -> bool:
    b = token.box
    return b.x <= EDGE_MARGIN or b.y <= EDGE_MARGIN or b.x + b.w >= 1 - EDGE_MARGIN or b.y + b.h >= 1 - EDGE_MARGIN


def add_cropped_edge(quality: ImageQuality, tokens: list[OcrToken]) -> ImageQuality:
    """Flag text running off the photo edge. Runs after OCR, on one image's tokens."""
    at_edge = sum(1 for t in tokens if _touches_edge(t))
    if "cropped_edge" in quality.issues or at_edge < EDGE_MIN_TOKENS or at_edge < EDGE_MIN_FRACTION * len(tokens):
        return quality
    issues: list[QualityIssue] = [*quality.issues, "cropped_edge"]
    return quality.model_copy(update={"issues": issues, "ok": False})
