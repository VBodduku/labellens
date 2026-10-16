"""The green veg mark is trusted only where the photo is green (acceptance-test regression)."""
from PIL import Image, ImageDraw

from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.veg_mark import checked_veg_mark, green_ratio
from backend.tests.fixture_data import scan_result
from shared.contract import Box, Evidence, LabelExtraction, VegMark

PURPLE = (113, 62, 175)
GREEN = (20, 150, 60)
MARK = Box(x=0.40, y=0.40, w=0.10, h=0.10)


def photo(with_mark: bool) -> PreparedImage:
    image = Image.new("RGB", (400, 400), PURPLE)
    if with_mark:
        draw = ImageDraw.Draw(image)
        draw.rectangle((160, 160, 199, 199), outline=GREEN, width=3)
        draw.ellipse((170, 170, 189, 189), fill=GREEN)
    return PreparedImage(image_id="img_0", original_width=400, original_height=400, ocr_image=image)


def extraction_with(mark: VegMark) -> LabelExtraction:
    return scan_result().extraction.model_copy(update={"veg_mark": mark})


def located(value: str, box: Box = MARK) -> VegMark:
    return VegMark(value=value, evidence=Evidence(image_id="img_0", text=f"{value} mark", box=box, status="approximate"))


def test_green_ratio_separates_a_real_mark_from_none():
    assert green_ratio(photo(True).ocr_image, MARK) > 0.05
    assert green_ratio(photo(False).ocr_image, MARK) == 0.0


def test_a_located_green_mark_on_green_pixels_is_kept():
    checked = checked_veg_mark(extraction_with(located("veg")), [photo(True)])
    assert checked.veg_mark.value == "veg"


def test_a_loose_box_around_a_real_mark_is_kept():
    loose = Box(x=0.35, y=0.35, w=0.20, h=0.20)
    assert checked_veg_mark(extraction_with(located("veg", loose)), [photo(True)]).veg_mark.value == "veg"


def test_a_green_mark_the_photo_does_not_show_becomes_unclear():
    checked = checked_veg_mark(extraction_with(located("veg")), [photo(False)])
    assert checked.veg_mark == VegMark(value="unclear")


def test_a_non_veg_mark_is_never_downgraded():
    assert checked_veg_mark(extraction_with(located("non_veg")), [photo(False)]).veg_mark.value == "non_veg"


def test_unlocated_or_missing_marks_pass_through():
    for mark in (VegMark(value="not_found"), VegMark(value="unclear")):
        assert checked_veg_mark(extraction_with(mark), [photo(False)]).veg_mark == mark
