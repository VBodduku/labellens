from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from backend.app.pipeline import focus
from backend.app.pipeline.focus import Line, View, candidate_views, focus_and_read, render, to_full, to_full_frame
from backend.app.pipeline.images import decode_upload
from shared.contract import Box, Evidence, Ingredient, OcrToken


def close(a: Box, b: Box) -> bool:
    return all(abs(x - y) < 1e-6 for x, y in ((a.x, b.x), (a.y, b.y), (a.w, b.w), (a.h, b.h)))


@pytest.mark.parametrize(("view", "expected"), [
    (View(), Box(x=0, y=0, w=0.2, h=0.1)),
    (View(0.5, 0.5, 1, 1), Box(x=0.5, y=0.5, w=0.1, h=0.05)),
    (View(turns=1), Box(x=0.9, y=0, w=0.1, h=0.2)),         # counter-clockwise: view top-left = photo top-right
    (View(turns=2), Box(x=0.8, y=0.9, w=0.2, h=0.1)),
    (View(turns=3), Box(x=0, y=0.8, w=0.1, h=0.2)),
])
def test_view_boxes_map_back_to_the_photo(view: View, expected: Box) -> None:
    assert close(to_full(Box(x=0, y=0, w=0.2, h=0.1), view), expected)


@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_render_and_to_full_agree_on_real_pixels(turns: int) -> None:
    photo = Image.new("RGB", (800, 600), "white")
    photo.paste((255, 0, 0), (500, 120, 540, 200))
    view = View(0.25, 0.1, 0.875, 0.6, turns=turns)
    seen = np.asarray(render(photo, view))
    ys, xs = np.nonzero((seen[:, :, 0] > 200) & (seen[:, :, 1] < 60))
    h, w = seen.shape[:2]
    found = to_full(Box(x=xs.min() / w, y=ys.min() / h, w=(xs.max() + 1 - xs.min()) / w,
                        h=(ys.max() + 1 - ys.min()) / h), view)
    assert abs(found.x - 500 / 800) < 0.01 and abs(found.y - 120 / 600) < 0.01
    assert abs(found.w - 40 / 800) < 0.01 and abs(found.h - 80 / 600) < 0.01


def lines(*rows: tuple[float, float, float, float], vertical: bool = False) -> list[Line]:
    return [Line(*row, vertical=vertical) for row in rows]


def test_too_few_lines_read_the_photo_as_it_is() -> None:
    assert candidate_views(lines((0.1, 0.1, 0.3, 0.12)), 1000, 1000) == [View()]


def test_sideways_text_in_a_corner_is_cropped_and_turned_both_ways() -> None:
    column = lines(*[(0.60 + 0.02 * i, 0.50, 0.61 + 0.02 * i, 0.90) for i in range(6)], vertical=True)
    first, second = candidate_views(column, 1000, 1000)
    assert (first.turns, second.turns) == (1, 3)
    assert first.x0 == pytest.approx(0.57) and first.y0 == pytest.approx(0.47) and first.x1 == pytest.approx(0.74)


def test_text_filling_the_photo_is_not_cropped() -> None:
    page = lines(*[(0.05, 0.05 + 0.1 * i, 0.95, 0.08 + 0.1 * i) for i in range(10)])
    views = candidate_views(page, 1000, 1000)
    assert [(v.x0, v.y0, v.x1, v.y1, v.turns) for v in views] == [(0, 0, 1, 1, 0), (0, 0, 1, 1, 2)]


def test_a_small_distant_text_block_is_kept_but_a_speck_is_not() -> None:
    ingredients = lines(*[(0.10, 0.10 + 0.03 * i, 0.40, 0.12 + 0.03 * i) for i in range(8)])
    nutrition = lines((0.10, 0.60, 0.25, 0.61), (0.10, 0.62, 0.25, 0.63))           # ~8 % of the main block
    speck = lines((0.90, 0.95, 0.905, 0.955))                                       # stray mark on the table
    view = candidate_views(ingredients + nutrition + speck, 1000, 1000)[0]
    assert view.y1 == pytest.approx(0.66) and view.x1 == pytest.approx(0.43)


def test_a_lone_statement_line_is_kept_but_a_big_background_shape_is_not() -> None:
    ingredients = lines(*[(0.10, 0.10 + 0.03 * i, 0.40, 0.12 + 0.03 * i) for i in range(8)])
    contains = lines((0.10, 0.80, 0.40, 0.815))                                    # "Contains: milk", far below
    tile = lines((0.70, 0.05, 0.85, 0.20))                                         # a square pattern on the cloth
    view = candidate_views(ingredients + contains + tile, 1000, 1000)[0]
    assert view.y1 == pytest.approx(0.845) and view.x1 == pytest.approx(0.43)


def test_to_full_frame_moves_every_evidence_and_token_box() -> None:
    box = Box(x=0, y=0, w=0.2, h=0.1)
    ingredient = Ingredient(id="ing_0", raw_text="Sugar", name="Sugar", sub_ingredients=[
        Ingredient(id="ing_0_0", raw_text="Cane", name="Cane",
                   evidence=[Evidence(image_id="img_0", text="Cane", box=box, status="verified")])])
    token = OcrToken(token_id="img_1:t0", image_id="img_1", text="Salt", box=box, confidence=0.9)
    views = {"img_0": View(turns=1), "img_1": View()}
    moved = to_full_frame(ingredient, views)
    assert close(moved.sub_ingredients[0].evidence[0].box, Box(x=0.9, y=0, w=0.1, h=0.2))   # type: ignore[arg-type]
    assert to_full_frame(token, views) is token                                     # an untouched photo stays as is
    assert to_full_frame(ingredient, {"img_0": View()}) is ingredient


def busy_table(size: tuple[int, int], seed: int = 7) -> Image.Image:
    """A cluttered, many-coloured background: no single colour to separate the pack from."""
    rng = np.random.default_rng(seed)
    pixels = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    pixels[:] = np.linspace(40, 200, size[0], dtype=np.uint8)[None, :, None]
    for _ in range(60):
        x, y = rng.integers(0, size[0] - 60), rng.integers(0, size[1] - 60)
        w, h = rng.integers(30, 200), rng.integers(30, 200)
        pixels[y:y + h, x:x + w] = rng.integers(0, 255, 3)
    return Image.fromarray(pixels)


def test_a_sideways_label_on_a_busy_table_is_found_turned_and_read(label_image: Image.Image) -> None:
    label = label_image.transpose(Image.Transpose.ROTATE_270)          # reads top to bottom, as on a cone
    label = label.resize((label.width * 6 // 10, label.height * 6 // 10), Image.Resampling.LANCZOS)
    photo = busy_table((2000, 1500))
    left, top = 1100, 700
    photo.paste(label, (left, top))
    buffer = io.BytesIO()
    photo.save(buffer, format="JPEG", quality=92)

    read = focus_and_read(decode_upload(buffer.getvalue(), "img_0"))
    assert read.view.turns == 1 and not read.view.identity
    words = " ".join(t.text for t in read.tokens).lower()
    assert "peanuts" in words and "ingredients" in words
    heading = next(t for t in read.tokens if t.text.lower().startswith("ingredients"))
    on_photo = to_full(heading.box, read.view)
    assert left / 2000 - 0.01 <= on_photo.x <= (left + label.width) / 2000
    assert top / 1500 - 0.01 <= on_photo.y <= (top + label.height) / 1500


def test_focus_falls_back_to_the_whole_photo_when_no_text_is_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(focus, "detect_lines", lambda image: [])
    image = decode_upload(_png(Image.new("RGB", (400, 300), "white")), "img_0")
    read = focus_and_read(image)
    assert read.view.identity and read.image is image


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
