"""OCR-only nutrition: columns from the header, side-by-side layouts, and numbers used only when corroborated.
Rows are modelled on RapidOCR output from real packets (Yoga Bar, Frooti, two-column namkeen packs)."""
from __future__ import annotations

from collections.abc import Sequence

from backend.app.pipeline.ocr_nutrition import find_nutrition
from backend.app.pipeline.ocr_only import product_name
from backend.tests.fakes import line_tokens, token
from shared.contract import NutritionTable, OcrToken


def table(lines: Sequence[Sequence[str]], x0: float = 0.05) -> list[OcrToken]:
    tokens: list[OcrToken] = []
    for n, words in enumerate(lines):
        tokens += line_tokens(list(words), 0.05 + n * 0.04, start=len(tokens), x0=x0)
    return tokens


def values(nutrition: NutritionTable | None, key: str) -> list[tuple[str, float | None, str]]:
    assert nutrition is not None
    row = next(r for r in nutrition.rows if r.key == key)
    return [(v.basis, v.amount, v.readability) for v in row.values]


YOGA_BAR = [
    ["Nutritional", "Facts"], ["Serving", "Size:35g"], ["Number", "of", "servings", "perRDAy"],
    ["Energy", "(Kcal)", "137", "7%"], ["Protein(g)", "3.8", "7%"], ["TotalFat(g)", "4.0", "6%"],
    ["Carbohydrate(g)", "23.5"], ["Total", "Sugar(g)", "10.8"], ["Sodium(mg)", "38.5", "2%"],
]


def test_a_per_serving_column_whose_energy_adds_up_is_used() -> None:
    nutrition = find_nutrition(table(YOGA_BAR))
    assert nutrition is not None and (nutrition.serving_size, nutrition.serving_unit) == (35.0, "g")
    assert values(nutrition, "energy_kcal") == [("per_serving", 137.0, "clear")]       # %RDA dropped
    assert values(nutrition, "carbohydrate_g") == [("per_serving", 23.5, "clear")]
    assert values(nutrition, "sodium_mg") == [("per_serving", 38.5, "clear")]


def test_numbers_that_do_not_add_up_stay_check_the_pack() -> None:
    misread = [line if line[0] != "Energy" else ["Energy", "(Kcal)", "731"] for line in YOGA_BAR]
    nutrition = find_nutrition(table(misread))
    assert all(v.readability == "partial" for r in nutrition.rows for v in r.values)  # type: ignore[union-attr]


def test_low_confidence_and_impossible_values_are_not_carried_by_the_energy_check() -> None:
    tokens = table(YOGA_BAR + [["Added", "Sugar(g)", "47"], ["Dietary", "Fibre", "(g)", "4.0"]])
    tokens[-1] = tokens[-1].model_copy(update={"confidence": 0.6})
    nutrition = find_nutrition(tokens)
    assert values(nutrition, "added_sugars_g") == [("per_serving", 47.0, "partial")]  # more than total sugars
    assert values(nutrition, "fibre_g") == [("per_serving", 4.0, "partial")]          # OCR unsure


def test_per_100_and_per_serving_columns_corroborate_each_other() -> None:
    nutrition = find_nutrition(table([
        ["NUTRITIONAL", "INFORMATION"], ["Per", "PerServe", "%RDA"], ["100g", "(20", "g)", "per", "serve"],
        ["Sodium", "(mg)", "750.2", "150.0", "7.5"], ["Total", "Fat(g)", "30.1", "6.0", "9.0"],
        ["Protein", "(g)", "5.7", "9.1"],
    ]))
    assert nutrition is not None and nutrition.serving_size == 20.0
    assert values(nutrition, "sodium_mg") == [("per_100g", 750.2, "clear"), ("per_serving", 150.0, "clear")]
    assert values(nutrition, "protein_g") == [("per_100g", 5.7, "partial"), ("per_serving", 9.1, "partial")]


def test_rda_per_serving_header_is_not_a_serving_column() -> None:
    nutrition = find_nutrition(table([["NutritionalInformation", "#Per100g", "RDAperservng"],
                                      ["PROTEIN", "5", "9", "2%"]]))
    assert values(nutrition, "protein_g") == [("per_100g", 5.0, "partial")]


def test_rows_beside_an_ingredient_list_are_read_and_list_words_are_not() -> None:
    left = line_tokens(["SUBSTANCES,", "TOMATO", "POWDER,", "PROTEIN,", "GARLIC", "AND", "100g"], 0.3)
    right = line_tokens(["Carbohydrate(g)", "65.3", "13.1"], 0.34, start=20, x0=0.6)
    listed = line_tokens(["SALT,", "SUGAR", "100g", "(20", "g)"], 0.38, start=40)
    nutrition = find_nutrition([token(60, "NUTRITIONAL", 0.6, 0.26), *left, *right, *listed])
    assert nutrition is not None and [r.key for r in nutrition.rows] == ["carbohydrate_g"]


def test_a_later_word_on_the_line_is_not_taken_as_the_label() -> None:
    nutrition = find_nutrition(table([["Trans", "Fat", "(o)", "0.0"], ["Total", "Fat", "(g)", "7.2"]]))
    assert values(nutrition, "trans_fat_g")[0][1] == 0.0
    assert values(nutrition, "total_fat_g")[0][1] == 7.2


def test_a_smudged_value_keeps_its_column_and_is_unreadable() -> None:
    nutrition = find_nutrition(table([["Per", "100", "g", "Per", "serving"], ["Sodium", "1?5", "？?"]]))
    assert values(nutrition, "sodium_mg") == [("per_100g", None, "unreadable"), ("per_serving", None, "unreadable")]


def test_product_name_is_the_large_confident_wording_only() -> None:
    small = table([["THERMALLY", "PROCESSED"], ["READY", "TO", "SERVE"], ["STORE", "IN", "A", "COOL", "PLACE"]])
    brand = [token(90, "FROOTI", 0.3, 0.6, h=0.1)]
    price = [token(91, "MRP", 0.3, 0.8, h=0.12), token(92, "Rs", 0.4, 0.8, h=0.12)]
    assert product_name(small + brand + price) == "FROOTI"
    assert product_name(small + price) is None
    unsure = [brand[0].model_copy(update={"confidence": 0.7})]
    assert product_name(small + unsure) is None
