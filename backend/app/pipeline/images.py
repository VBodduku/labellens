"""Decode uploaded photos: validate format, apply EXIF orientation, convert to RGB, resize."""
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

OCR_MAX_SIDE = 2000
LLM_MAX_SIDE = 1600
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP", "HEIF"}


class BadImageError(ValueError):
    """The upload is not a usable photo. The message is safe to show to the user."""


@dataclass(frozen=True)
class PreparedImage:
    image_id: str
    original_width: int             # after EXIF orientation, before resizing
    original_height: int
    ocr_image: Image.Image          # RGB, long side <= OCR_MAX_SIDE

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


def decode_upload(data: bytes, image_id: str) -> PreparedImage:
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format not in ALLOWED_FORMATS:
                raise BadImageError(f"Unsupported image type {opened.format or 'unknown'}; use JPEG, PNG or WebP.")
            oriented = ImageOps.exif_transpose(opened)
            rgb = oriented.convert("RGB")
    except BadImageError:
        raise
    except Image.DecompressionBombError as exc:
        raise BadImageError("The image has too many pixels.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise BadImageError("The file is not a readable image (JPEG, PNG or WebP).") from exc
    return PreparedImage(
        image_id=image_id,
        original_width=rgb.width,
        original_height=rgb.height,
        ocr_image=resized(rgb, OCR_MAX_SIDE),
    )
