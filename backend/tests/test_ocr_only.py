"""OCR-only degraded mode: keyword rules over real OCR tokens of the fixture label."""
from __future__ import annotations

from backend.app.pipeline.ocr_only import extract_panel, find_ingredients, find_statements
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


def _page(*columns: list[tuple[list[str], float]], x0s: tuple[float, ...] = (0.05, 0.7)) -> list[OcrToken]:
    """Side-by-side columns of printed lines, interleaved in reading order like real OCR output."""
    tokens: list[OcrToken] = []
    for column, x0 in zip(columns, x0s):
        for words, y in column:
            tokens += line_tokens(words, y, start=len(tokens), x0=x0)
    return sorted(tokens, key=lambda t: (t.box.y, t.box.x))


def test_heading_graphic_is_not_a_contains_statement() -> None:
    graphic = [(["THIS", "BAR"], 0.10), (["CONTAINS"], 0.12), (["No", "Artificial", "Flavours"], 0.14)]
    ingredients = [(["Ingredients:", "Oats,", "Honey,"], 0.10), (["Peanut", "Butter,", "Salt."], 0.12)]
    assert find_statements(_page(graphic, ingredients)) == []


def test_statements_stay_in_their_own_column() -> None:
    allergens = [(["Allergen", "Advice:"], 0.50), (["CONTAINS", "OATS,", "NUTS"], 0.52),
                 (["SOY.", "Processed", "in", "a", "plant"], 0.54), (["where", "other", "tree", "nuts", "are"], 0.56),
                 (["processed."], 0.58), (["Manufactured", "by", "Foods", "Ltd"], 0.64)]
    nutrition = [(["Total", "Fat", "4.0"], 0.50), (["Sodium", "38.5"], 0.52), (["Protein", "3.8"], 0.54),
                 (["Sugar", "10.8"], 0.56), (["Fibre", "4.0"], 0.58)]
    contains, facility = find_statements(_page(allergens, nutrition))
    assert (contains.type, contains.items) == ("contains", ["OATS", "NUTS", "SOY"])
    assert contains.raw_text == "Allergen Advice: CONTAINS OATS, NUTS SOY."
    assert (facility.type, facility.items) == ("facility", ["tree nuts"])
    evidence = " ".join(e.text for s in (contains, facility) for e in s.evidence)
    assert not any(word in evidence for word in ("Fat", "Sodium", "Protein", "Manufactured"))


def test_contains_that_is_not_a_short_list_is_left_out() -> None:
    tokens = line_tokens(["Contains:", "Rolled", "oats", "baked", "with", "honey", "for", "120", "minutes."], 0.1)
    assert find_statements(tokens) == []


def test_contains_opening_its_own_line_counts_even_without_a_full_stop_before() -> None:
    tokens = (line_tokens(["Natural", "Flavours"], 0.10)
              + line_tokens(["CONTAINSMILK,SOY.MAYCONTAIN", "WHEAT,", "BARLEY."], 0.12, start=2))
    assert [(s.type, s.items) for s in find_statements(tokens)] == [
        ("contains", ["MILK", "SOY"]), ("may_contain", ["WHEAT", "BARLEY"])]
