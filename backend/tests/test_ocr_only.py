"""OCR-only degraded mode: keyword rules over real OCR tokens of the fixture label."""
from __future__ import annotations

from backend.app.pipeline.ocr_only import extract_panel, find_ingredients
from backend.tests.fakes import line_tokens
from shared.contract import OcrToken


def test_reads_fixture_label_honestly(label_tokens: list[OcrToken]) -> None:
    panel = extract_panel("img_0", label_tokens)
    names = [i.name for i in panel.ingredients]
    assert names[:4] == ["Sugar", "Peanuts (22%)", "Milk Solids (12%)", "Refined Wheat Flour (Maida)"]
    assert names[-1] == "Natural Flavours" and len(names) == 11
    assert panel.ingredients[1].percentage == 22.0
    assert all(i.readability == "partial" and i.evidence[0].status == "verified" for i in panel.ingredients)

    assert [(s.type, s.items) for s in panel.allergen_statements] == [
        ("contains", ["PEANUT", "MILK", "WHEAT", "SOY"]), ("may_contain", ["TREE NUTS"])]

    rows = {r.key: r for r in panel.nutrition.rows}  # type: ignore[union-attr]
    assert [(v.basis, v.amount, v.unit) for v in rows["energy_kcal"].values] == [
        ("per_100g", 520.0, "kcal"), ("per_serving", 208.0, "kcal")]
    assert rows["total_sugars_g"].values[0].amount == 38.0
    assert [v.amount for v in rows["sodium_mg"].values] == [None, None]
    # The energy adds up and both columns agree through the 40 g serving, so the numbers are usable.
    assert all(v.readability == "clear" for key in ("energy_kcal", "total_sugars_g") for v in rows[key].values)

    for section in (panel.ingredients_section, panel.allergen_section, panel.nutrition_section):
        assert section.complete is False and "ocr_only" in section.issues
    assert panel.veg_mark.value == "unclear"


def test_compound_ingredients_stay_together_and_heading_remainder_counts() -> None:
    tokens = line_tokens(["Ingredients:Wheat", "Flour,", "Chocolate", "(Sugar,", "Cocoa),", "Salt."], 0.1)
    ingredients, found = find_ingredients(tokens)
    assert found
    assert [i.name for i in ingredients] == ["Wheat Flour", "Chocolate (Sugar, Cocoa)", "Salt"]


def test_no_heading_means_section_not_found() -> None:
    panel = extract_panel("img_0", line_tokens(["Best", "before", "6", "months"], 0.1))
    assert panel.ingredients == [] and panel.ingredients_section.presence == "not_found"
    assert panel.nutrition is None
