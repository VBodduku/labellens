from __future__ import annotations

import pytest

from backend.app.pipeline.ocr import CharBox, OcrLine, order_lines, parse_raw, split_line, tokens_from_lines


def line(x0: float, y0: float, x1: float, y1: float, text: str, score: float = 0.9) -> OcrLine:
    return OcrLine(x0, y0, x1, y1, text, score)


def test_split_line_distributes_width_by_characters() -> None:
    words = split_line(line(100, 10, 200, 30, "ab cdef"))
    assert [w.text for w in words] == ["ab", "cdef"]
    assert words[0].x0 == pytest.approx(100)
    assert words[0].x1 == pytest.approx(100 + 100 * 2 / 7)
    assert words[1].x0 == pytest.approx(100 + 100 * 3 / 7)
    assert words[1].x1 == pytest.approx(200)
    assert all(w.y0 == 10 and w.y1 == 30 and w.score == 0.9 for w in words)


def test_split_line_handles_repeated_words_and_extra_spaces() -> None:
    words = split_line(line(0, 0, 100, 10, "  Per  100 g  Per "))
    assert [w.text for w in words] == ["Per", "100", "g", "Per"]
    assert words[0].x1 < words[1].x0 < words[2].x0 < words[3].x0
    assert words[3].x0 == pytest.approx(100 * 14 / 18)


def quad(x0: float, x1: float, y0: float = 10, y1: float = 40) -> list[list[float]]:
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_split_line_uses_char_gaps_to_restore_dropped_spaces() -> None:
    # "TotalFat": recogniser dropped the space, but the gap after "l" is wide (21 px on a 30 px line).
    xs = [(61, 76), (77, 90), (90, 100), (100, 112), (112, 124), (145, 158), (159, 170), (171, 182)]
    raw = [[quad(57, 186), "TotalFat", 0.97, [quad(a, b) for a, b in xs], list("TotalFat"), [0.9] * 8]]
    words = split_line(parse_raw(raw)[0])
    assert [w.text for w in words] == ["Total", "Fat"]
    assert (words[0].x0, words[0].x1) == (61, 124)
    assert (words[1].x0, words[1].x1) == (145, 182)


def test_split_line_char_boxes_split_on_space_characters() -> None:
    chars = (CharBox("5", 0, 0, 10, 20), CharBox("8", 10, 0, 20, 20), CharBox(" ", 20, 0, 25, 20),
             CharBox("g", 26, 0, 34, 20))
    words = split_line(OcrLine(0, 0, 34, 20, "58 g", 0.9, chars))
    assert [(w.text, w.x0, w.x1) for w in words] == [("58", 0, 20), ("g", 26, 34)]


def test_parse_raw_ignores_char_boxes_that_do_not_match_chars() -> None:
    raw = [[quad(0, 100), "ab cd", 0.9, [quad(0, 10)], list("ab cd"), [0.9] * 5]]
    words = split_line(parse_raw(raw)[0])
    assert [w.text for w in words] == ["ab", "cd"]
    assert words[1].x1 == 100


def test_parse_raw_converts_quads_to_boxes_and_skips_blank_text() -> None:
    raw = [
        [[[10, 20], [110, 18], [112, 40], [12, 42]], "Sugar,", "0.98"],
        [[[0, 0], [5, 0], [5, 5], [0, 5]], "  ", 0.5],
    ]
    lines = parse_raw(raw)
    assert lines == [OcrLine(10, 18, 112, 42, "Sugar,", 0.98)]
    assert parse_raw(None) == []


def test_reading_order_rows_then_columns_with_slight_rotation() -> None:
    lines = [
        line(500, 104, 700, 124, "right"),   # same row as "left", a few px lower (rotation)
        line(10, 150, 300, 170, "second"),
        line(10, 100, 300, 120, "left"),
        line(10, 10, 300, 30, "title"),
    ]
    assert [l.text for l in order_lines(lines)] == ["title", "left", "right", "second"]


def test_tokens_get_ids_in_reading_order_and_normalised_clamped_boxes() -> None:
    lines = [
        line(0, 50, 100, 60, "Contains: Milk"),
        line(-5, 0, 1010, 20, "Nutrition"),
    ]
    tokens = tokens_from_lines(lines, "img_1", 1000, 100)
    assert [(t.token_id, t.text) for t in tokens] == [
        ("img_1:t0", "Nutrition"), ("img_1:t1", "Contains:"), ("img_1:t2", "Milk"),
    ]
    first = tokens[0].box
    assert (first.x, first.y, first.w, first.h) == (0.0, 0.0, 1.0, 0.2)
    assert all(t.image_id == "img_1" for t in tokens)
    assert tokens_from_lines([], "img_0", 10, 10) == []
