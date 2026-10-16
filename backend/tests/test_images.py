from __future__ import annotations

import io

import pytest
from PIL import Image

from backend.app.pipeline.images import BadImageError, decode_upload, image_id

EXIF_ORIENTATION = 0x0112


def encode(image: Image.Image, fmt: str, **kwargs: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def test_exif_rotation_is_applied() -> None:
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6   # rotate 90 degrees clockwise to display
    data = encode(Image.new("RGB", (800, 600), "white"), "JPEG", exif=exif)
    prepared = decode_upload(data, "img_0")
    assert (prepared.original_width, prepared.original_height) == (600, 800)
    assert prepared.ocr_image.mode == "RGB"


def test_large_photo_is_resized_for_ocr_and_llm() -> None:
    data = encode(Image.new("RGB", (3000, 1500), "white"), "PNG")
    prepared = decode_upload(data, "img_1")
    assert (prepared.original_width, prepared.original_height) == (3000, 1500)
    assert (prepared.width, prepared.height) == (2000, 1000)
    assert max(prepared.for_llm().size) == 1600


def test_rgba_webp_is_accepted() -> None:
    data = encode(Image.new("RGBA", (700, 700), (10, 20, 30, 128)), "WEBP")
    assert decode_upload(data, "img_0").ocr_image.mode == "RGB"


@pytest.mark.parametrize("data", [b"not an image at all", encode(Image.new("RGB", (50, 50)), "GIF")])
def test_unusable_files_are_rejected(data: bytes) -> None:
    with pytest.raises(BadImageError):
        decode_upload(data, "img_0")


def test_image_ids_follow_upload_order() -> None:
    assert [image_id(i) for i in range(3)] == ["img_0", "img_1", "img_2"]
