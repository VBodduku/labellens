"""Decode uploaded photos: validate format, apply EXIF orientation, convert to RGB, resize."""
from __future__ import annotations

import io
from dataclasses import dataclass

import math

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()          # iPhone HEIC/HEIF photos

OCR_MAX_SIDE = 2000
SOURCE_MAX_SIDE = 4000
LLM_MAX_SIDE = 1600
MAX_PIXELS = 50_000_000         # refuse before decoding: a 50 MP+ upload is not a label photo
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}
EXIF_ORIENTATION = 0x0112
_SWAPS_AXES = {5, 6, 7, 8}      # EXIF orientations that rotate by 90 degrees


class BadImageError(ValueError):
    """The upload is not a usable photo. The message is safe to show to the user."""


@dataclass(frozen=True)
class PreparedImage:
    image_id: str
    original_width: int             # after EXIF orientation, before resizing
    original_height: int
    ocr_image: Image.Image          # RGB, long side <= OCR_MAX_SIDE
    source: Image.Image | None = None   # sharper RGB copy (long side <= SOURCE_MAX_SIDE) to crop small print from

    @property
    def width(self) -> int:
        return self.ocr_image.width

    @property
    def height(self) -> int:
        return self.ocr_image.height

    def for_llm(self) -> Image.Image:
        return resized(self.ocr_image, LLM_MAX_SIDE)


def image_id(index: int) -> str:
    return f"img_{index}"


def resized(image: Image.Image, max_side: int) -> Image.Image:
    long_side = max(image.size)
    if long_side <= max_side:
        return image.copy()
    scale = max_side / long_side
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    return image.resize(size, Image.Resampling.LANCZOS)


def _draft_size(width: int, height: int) -> tuple[int, int]:
    """Smallest size JPEG draft decoding may return while the long side stays >= SOURCE_MAX_SIDE."""
    scale = SOURCE_MAX_SIDE / max(width, height)
    return math.ceil(width * scale), math.ceil(height * scale)


def decode_upload(data: bytes, image_id: str) -> PreparedImage:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format not in ALLOWED_FORMATS:
                raise BadImageError(f"Unsupported image type {opened.format or 'unknown'}; use JPEG, PNG or WebP.")
            width, height = opened.size
            if width * height > MAX_PIXELS:
                raise BadImageError("The photo has too many pixels (over 50 megapixels).")
            orientation = opened.getexif().get(EXIF_ORIENTATION, 1)
            original = (height, width) if orientation in _SWAPS_AXES else (width, height)
            if opened.format in ("JPEG", "MPO") and max(width, height) > SOURCE_MAX_SIDE:
                opened.draft("RGB", _draft_size(width, height))     # decode big phone JPEGs at reduced scale
            oriented = ImageOps.exif_transpose(opened)
            rgb = oriented.convert("RGB")
    except BadImageError:
        raise
    except Image.DecompressionBombError as exc:
        raise BadImageError("The photo has too many pixels (over 50 megapixels).") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise BadImageError("The file is not a readable image (JPEG, PNG, WebP or HEIC).") from exc
    ocr = resized(rgb, OCR_MAX_SIDE)
    return PreparedImage(
        image_id=image_id,
        original_width=original[0],
        original_height=original[1],
        ocr_image=ocr,
        source=resized(rgb, SOURCE_MAX_SIDE) if max(rgb.size) > OCR_MAX_SIDE else None,
    )
