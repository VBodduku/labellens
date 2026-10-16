"""Evidence alignment (spec §4.4): the core of "every flag points at the words on the photo"."""
from __future__ import annotations

import json

import pytest

from backend.app.pipeline.align import (
    TokenIndex,
    align_panel,
    align_span,
    box_from_2d,
    panel_image_ids,
    split_lines,
)
from backend.app.pipeline.llm_schema import LLMExtraction, LLMPanel
from backend.tests.fakes import line_tokens, recorded

LINE_1 = ["INGREDIENTS:", "Sugar,", "Peanuts", "(22%),", "Milk", "Solids", "(12%),"]
LINE_2 = ["Invert", "Sugar", "Syrup,", "Emulsifier", "(INS", "322", "[Soy]),", "Salt."]
LINE_3 = ["Energy", "520", "kcal", "Sodium", "1?5", "mg"]


def tokens() -> list:
    first = line_tokens(LINE_1, 0.20)
    second = line_tokens(LINE_2, 0.25, start=len(first))
    third = line_tokens(LINE_3, 0.60, start=len(first) + len(second))
    return first + second + third


INDEX = TokenIndex(tokens())
CITES = [t.token_id for t in tokens()]          # the model's word number n -> img_0:tn


def ids(*numbers: int) -> list[str]:
    return [f"img_0:t{n}" for n in numbers]


def nums(*numbers: int) -> list[int]:
    """What the model cites in its JSON: word numbers."""
    return list(numbers)


def section(**overrides: object) -> dict:
    return {"presence": "found", "complete": True, "issues": [], "unreadable_token_ids": [],
            "unreadable_boxes": [], **overrides}


def panel(**overrides: object) -> LLMPanel:
    data = {
        "image_id": "img_0", "ingredients": [], "ingredients_section": section(),
        "allergen_statements": [], "allergen_section": section(presence="not_found", complete=False),
        "nutrition": None, "nutrition_section": section(presence="not_found", complete=False),
        "veg_mark": {"value": "not_found", "box_2d": None}, "claims": [], **overrides,
    }
    return LLMPanel.model_validate(data)


# ---------------------------------------------------------------- align_span statuses
def test_cited_tokens_that_match_are_verified() -> None:
    result = align_span("Peanuts (22%)", ids(2, 3), None, "img_0", INDEX)
    assert result.status == "verified"
    assert result.ocr_text == "Peanuts (22%),"
    [evidence] = result.evidence
    assert evidence.token_ids == ids(2, 3)
    assert evidence.text == "Peanuts (22%),"
    assert evidence.match_score >= 0.85
    assert evidence.box is not None and evidence.box.x == pytest.approx(INDEX.by_id["img_0:t2"].box.x)


def test_wrong_citation_falls_back_to_window_search() -> None:
    result = align_span("Milk Solids (12%)", ids(0, 1), None, "img_0", INDEX)
    assert result.status == "verified"
    assert result.evidence[0].token_ids == ids(4, 5, 6)


def test_citation_far_too_wide_is_not_accepted_as_is() -> None:
    # Citing the whole line for "Sugar" would highlight the line; the window search narrows it.
    result = align_span("Sugar", ids(*range(0, 7)), None, "img_0", INDEX)
    assert result.status == "verified"
    assert result.evidence[0].token_ids == ids(1)


def test_short_window_inside_longer_text_is_not_a_match() -> None:
    # "Sugar" alone must not verify "Invert Sugar Syrup Blend" (absent from the label).
    result = align_span("Invert Sugar Syrup Blend Extra", [], None, "img_0", INDEX)
    assert result.status == "unverified"


def test_window_search_prefers_occurrence_near_citation() -> None:
    # "Sugar" appears at t1 ("Sugar,") and t8; the cited neighbour decides.
    near_second = align_span("Sugar", ids(9), None, "img_0", INDEX)
    assert near_second.evidence[0].token_ids == ids(8)


def test_box_2d_gives_approximate_evidence() -> None:
    result = align_span("दूध", [], [100, 200, 150, 400], "img_0", INDEX)
    assert result.status == "approximate"
    [evidence] = result.evidence
    assert evidence.box is not None
    assert (evidence.box.x, evidence.box.y, evidence.box.w, evidence.box.h) == (0.2, 0.1, 0.2, 0.05)
    assert evidence.token_ids == [] and evidence.text == "दूध"
    assert result.confidence == 0.7


def test_nothing_found_is_unverified_without_box() -> None:
    result = align_span("Hazelnut Paste", ["img_0:t999", "img_1:t1"], None, "img_0", INDEX)
    assert result.status == "unverified"
    assert result.evidence[0].box is None
    assert result.confidence == 0.4


def test_tokens_from_another_image_are_ignored() -> None:
    result = align_span("Peanuts (22%)", ids(2, 3), None, "img_1", INDEX)
    assert result.status == "unverified"


@pytest.mark.parametrize("box_2d", [None, [1, 2, 3], [500, 500, 400, 600], [0, 0, 0, 0]])
def test_malformed_boxes_are_ignored(box_2d: list[int] | None) -> None:
    assert box_from_2d(box_2d) is None


def test_box_values_are_clamped() -> None:
    box = box_from_2d([-20, 900, 1200, 1100])
    assert box is not None and (box.x, box.y, box.w, box.h) == (0.9, 0.0, 0.1, 1.0)


# ---------------------------------------------------------------- one Evidence per printed line
def test_span_across_two_lines_gives_one_evidence_per_line() -> None:
    result = align_span("Milk Solids (12%), Invert Sugar Syrup", ids(4, 5, 6, 7, 8, 9), None, "img_0", INDEX)
    assert result.status == "verified"
    assert [e.token_ids for e in result.evidence] == [ids(4, 5, 6), ids(7, 8, 9)]
    assert result.evidence[0].box.y != result.evidence[1].box.y  # type: ignore[union-attr]


def test_split_lines_breaks_when_x_goes_back() -> None:
    lines = split_lines(tokens())
    assert [len(line) for line in lines] == [len(LINE_1), len(LINE_2), len(LINE_3)]


# ---------------------------------------------------------------- numbers come from the photo
def test_nutrient_amount_is_parsed_from_ocr_text_not_llm() -> None:
    rows = [{"key": "energy_kcal", "label": "Energy", "values": [
        {"basis": "per_100g", "amount": 502, "unit": "kcal", "text": "520 kcal", "token_ids": nums(16, 17),
         "readability": "clear", "box_2d": None}]}]
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", INDEX, CITES)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.amount == 520
    assert value.raw_text == "520 kcal"
    assert value.evidence is not None and value.evidence.token_ids == ids(16, 17)
    assert "llm_ocr_number_mismatch:energy_kcal:per_100g:502" in p.nutrition_section.issues
    assert value.readability == "partial"           # the two readings disagree: not used until the user checks


def test_ocr_that_only_lost_the_decimal_point_agrees_with_the_model() -> None:
    from backend.app.pipeline.textnorm import number_digits
    assert number_digits("88") == number_digits("8.8") == "88"
    assert number_digits("520 kcal") != number_digits("502")


def test_smudged_value_is_unreadable_even_if_llm_guessed() -> None:
    rows = [{"key": "sodium_mg", "label": "Sodium", "values": [
        {"basis": "per_100g", "amount": 175, "unit": "mg", "text": "1?5 mg", "token_ids": nums(19, 20),
         "readability": "clear", "box_2d": None}]}]
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", INDEX, CITES)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.amount is None and value.readability == "unreadable"
    assert value.evidence is not None and value.evidence.status == "verified"
    assert p.nutrition_section.complete is False


def test_llm_marked_unreadable_value_has_no_amount() -> None:
    rows = [{"key": "sodium_mg", "label": "Sodium", "values": [
        {"basis": "per_100g", "amount": 150, "unit": "mg", "text": "", "token_ids": [],
         "readability": "unreadable", "box_2d": [600, 300, 620, 350]}]}]
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", INDEX, CITES)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.amount is None and value.evidence is not None and value.evidence.status == "approximate"


def test_value_not_on_photo_is_dropped_not_trusted() -> None:
    rows = [{"key": "protein_g", "label": "Protein", "values": [
        {"basis": "per_100g", "amount": 9.5, "unit": "g", "text": "9.5 g", "token_ids": [],
         "readability": "clear", "box_2d": None}]}]
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", INDEX, CITES)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.amount is None and value.readability == "unreadable"
    assert value.evidence is not None and value.evidence.status == "unverified"
    assert "value_not_on_photo:protein_g" in p.nutrition_section.issues
    assert p.nutrition_section.complete is False


def test_value_located_only_by_model_box_is_partial() -> None:
    rows = [{"key": "protein_g", "label": "Protein", "values": [
        {"basis": "per_100g", "amount": 9.5, "unit": "g", "text": "9.5 g", "token_ids": [],
         "readability": "clear", "box_2d": [600, 300, 620, 350]}]}]
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", INDEX, CITES)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.amount == 9.5 and value.readability == "partial"


def test_percentage_from_ocr_wins_with_issue() -> None:
    items = [{"text": "Peanuts (2.2%)", "token_ids": nums(2, 3), "percentage": 2.2, "parent_index": None,
              "readability": "clear", "box_2d": None}]
    p = align_panel(panel(ingredients=items), "img_0", INDEX, CITES)
    assert p.ingredients[0].percentage == 22.0
    assert "llm_ocr_number_mismatch" in p.ingredients_section.issues


# ---------------------------------------------------------------- ingredients and sections
def ingredient(text: str, token_ids: list[int], parent: int | None = None, readability: str = "clear") -> dict:
    return {"text": text, "token_ids": token_ids, "percentage": None, "parent_index": parent,
            "readability": readability, "box_2d": None}


def test_ingredients_raw_text_name_confidence_and_nesting() -> None:
    items = [
        ingredient("Sugar", nums(1)),
        ingredient("Emulsifier (INS 322 [Soy])", nums(10, 11, 12, 13)),
        ingredient("INS 322", nums(11, 12), parent=1),
        ingredient("Salt", nums(14)),
    ]
    p = align_panel(panel(ingredients=items), "img_0", INDEX, CITES)
    assert [i.name for i in p.ingredients] == ["Sugar", "Emulsifier (INS 322 [Soy])", "Salt"]
    assert p.ingredients[0].raw_text == "Sugar"
    assert p.ingredients[2].raw_text == "Salt."
    assert [s.name for s in p.ingredients[1].sub_ingredients] == ["INS 322"]
    assert all(i.confidence == 1.0 for i in p.ingredients)
    assert p.ingredients_section.complete is True


@pytest.mark.parametrize("parent", [0, 5, 2, -1])
def test_implausible_parents_are_ignored(parent: int) -> None:
    # 0: "Salt" is not inside "Sugar"; 5: out of range; 2: self; -1: invalid.
    items = [ingredient("Sugar", nums(1)), ingredient("Peanuts", nums(2)), ingredient("Salt", nums(14), parent=parent)]
    p = align_panel(panel(ingredients=items), "img_0", INDEX, CITES)
    assert [i.name for i in p.ingredients] == ["Sugar", "Peanuts", "Salt"]


def test_section_completeness_is_forced_false_by_unclear_items_or_regions() -> None:
    partial = align_panel(panel(ingredients=[ingredient("Sugar", nums(1), readability="partial")]), "img_0", INDEX, CITES)
    assert partial.ingredients_section.complete is False

    regions = align_panel(panel(ingredients_section=section(unreadable_token_ids=nums(19, 20),
                                                            unreadable_boxes=[{"box_2d": [10, 10, 20, 50]}])),
                          "img_0", INDEX, CITES)
    s = regions.ingredients_section
    assert s.complete is False and "unreadable_span" in s.issues
    assert [r.status for r in s.unreadable_regions] == ["verified", "approximate"]
    assert s.unreadable_regions[0].token_ids == ids(19, 20)

    missing = align_panel(panel(ingredients_section=section(presence="partial")), "img_0", INDEX, CITES)
    assert missing.ingredients_section.complete is False


def test_statements_claims_and_veg_mark() -> None:
    p = align_panel(panel(
        allergen_statements=[{"type": "contains", "text": "Milk Solids", "items": ["Milk"], "token_ids": nums(4, 5),
                              "box_2d": None}],
        claims=[{"text": "Energy", "token_ids": nums(15), "box_2d": None}],
        veg_mark={"value": "veg", "box_2d": [20, 860, 70, 940]},
    ), "img_0", INDEX, CITES)
    assert p.allergen_statements[0].raw_text == "Milk Solids"
    assert p.allergen_statements[0].evidence[0].status == "verified"
    assert p.claims[0].evidence[0].token_ids == ids(15)
    assert p.veg_mark.value == "veg" and p.veg_mark.evidence is not None
    assert p.veg_mark.evidence.status == "approximate"


@pytest.mark.parametrize("value, kept, status", [("veg", "unclear", None), ("non_veg", "non_veg", "unverified")])
def test_a_veg_mark_the_model_cannot_locate_never_loosens_a_verdict(value: str, kept: str, status: str | None) -> None:
    p = align_panel(panel(veg_mark={"value": value, "box_2d": None}), "img_0", INDEX, CITES)
    assert p.veg_mark.value == kept
    assert (p.veg_mark.evidence.status if p.veg_mark.evidence else None) == status


def test_panel_image_ids_repairs_bad_or_duplicate_ids() -> None:
    panels = [panel(image_id="img_1"), panel(image_id="img_1"), panel(image_id="front")]
    assert panel_image_ids(panels, ["img_0", "img_1", "img_2"]) == ["img_1", "img_0", "img_2"]


# ---------------------------------------------------------------- a real recorded model response
def test_recorded_ollama_response_on_test_label(label_tokens: list) -> None:
    extraction = LLMExtraction.model_validate(json.loads(recorded("ollama_test_label.json")))
    p = align_panel(extraction.panels[0], "img_0", TokenIndex(label_tokens), [t.token_id for t in label_tokens])
    names = [i.name for i in p.ingredients]
    assert names[:3] == ["Sugar", "Peanuts (22%)", "Milk Solids (12%)"]          # bogus parent_index=0 ignored
    assert p.evidence_count["verified"] >= 0.8 * sum(p.evidence_count.values())
    sodium = next(r for r in p.nutrition.rows if r.key == "sodium_mg")  # type: ignore[union-attr]
    assert sodium.values[0].amount is None                                        # model invented "175 mg"
    assert p.nutrition_section.complete is False


# A small table: three rows on three printed lines (the covered-table re-read of Test 3, docs/TEST_RESULTS.md).
TABLE = (line_tokens(["Total", "Sugars", "3.1", "0.6"], 0.10) + line_tokens(["Total", "Fat", "24.1", "4.8"], 0.14, start=4)
         + line_tokens(["Protein", "6.9", "1.4"], 0.18, start=8))
TABLE_INDEX = TokenIndex(TABLE)
TABLE_CITES = [t.token_id for t in TABLE]


def table_row(key: str, label: str, amount: float, cite: int) -> dict:
    return {"key": key, "label": label, "values": [{"basis": "per_100g", "amount": amount, "unit": "g", "text": f"{amount:g}",
                                                     "token_ids": [cite], "readability": "clear", "box_2d": None}]}


def aligned_table(*rows: dict):  # type: ignore[no-untyped-def]
    return align_panel(panel(nutrition={"rows": list(rows)}, nutrition_section=section()), "img_0", TABLE_INDEX,
                       TABLE_CITES)


def test_a_value_from_another_row_is_not_used_for_this_row() -> None:
    p = aligned_table(table_row("total_fat_g", "Total Fat", 3.1, 2))        # 3.1 is printed, on the sugars line
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert (value.amount, value.readability) == (3.1, "partial")
    assert "value_off_row:total_fat_g" in p.nutrition_section.issues


def test_a_row_whose_label_is_not_on_the_photo_is_never_used() -> None:
    p = aligned_table(table_row("sodium_mg", "Sodium (mg)", 24.1, 6))       # a covered row, given Fat's number
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert value.readability == "partial"
    assert "row_not_on_photo:sodium_mg" in p.nutrition_section.issues


def test_the_same_number_on_the_right_line_is_used_instead() -> None:
    tokens = TABLE + line_tokens(["Saturated", "Fat", "0.6", "0.1"], 0.22, start=len(TABLE))
    cites = [t.token_id for t in tokens]
    rows = [table_row("saturated_fat_g", "Saturated Fat", 0.6, 3)]           # cites the sugars line's 0.6
    p = align_panel(panel(nutrition={"rows": rows}, nutrition_section=section()), "img_0", TokenIndex(tokens), cites)
    value = p.nutrition.rows[0].values[0]  # type: ignore[union-attr]
    assert (value.amount, value.readability) == (0.6, "clear")
    assert value.evidence is not None and value.evidence.token_ids == ["img_0:t13"]   # its own line's 0.6
