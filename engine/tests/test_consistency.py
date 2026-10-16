from collections.abc import Callable

import pytest
from shared.contract import LabelExtraction, NutritionTable, NutrientRow, NutrientValue
from engine.nutrition import analyze_nutrition, correction_candidates, value_at_basis


def label(
    make_extraction: Callable[..., LabelExtraction],
    energy: float = 522,
    protein: float = 9.5,
    carbs: float = 58,
    fat: float = 28,
    basis: str = "per_100g",
) -> LabelExtraction:
    extraction = make_extraction("salt")
    extraction.nutrition_section.presence = "found"
    extraction.nutrition = NutritionTable(
        rows=[
            NutrientRow(
                key=key,
                raw_label=name,
                values=[
                    NutrientValue(
                        basis=basis,
                        amount=amount,
                        unit=unit,
                        raw_text=f"{amount} {unit}",
                    )
                ],
            )
            for key, name, amount, unit in [
                ("energy_kcal", "Energy", energy, "kcal"),
                ("protein_g", "Protein", protein, "g"),
                ("carbohydrate_g", "Carbohydrate", carbs, "g"),
                ("total_fat_g", "Total fat", fat, "g"),
            ]
        ]
    )
    return extraction


def add(
    extraction: LabelExtraction,
    key: str,
    amount: float,
    raw_label: str = "",
    basis: str = "per_100g",
    unit: str = "g",
) -> None:
    assert extraction.nutrition
    extraction.nutrition.rows.append(
        NutrientRow(
            key=key,
            raw_label=raw_label or key,
            values=[
                NutrientValue(
                    basis=basis, amount=amount, unit=unit, raw_text=f"{amount} {unit}"
                )
            ],
        )
    )


@pytest.mark.parametrize(
    "energy,protein,carbs,fat,state",
    [
        (520, 9.5, 58, 28, "consistent"),
        (100, 0, 28.75, 0, "consistent"),
        (100, 0, 28.753, 0, "inconsistent"),
        (0, 0, 0, 0, "consistent"),
        (0, 5, 5, 5, "inconsistent"),
        (240, 10, 30, 8.88888889, "consistent"),
        (522, 9.5, 58, 2.8, "inconsistent"),
    ],
)
def test_energy_formula_and_fifteen_percent_boundary(
    make_extraction, energy, protein, carbs, fat, state
):
    analysis = analyze_nutrition(label(make_extraction, energy, protein, carbs, fat))
    assert analysis.consistency.status == state
    assert analysis.consistency.computed_kcal == pytest.approx(
        4 * protein + 4 * carbs + 9 * fat
    )
    if energy == 0 and analysis.consistency.computed_kcal > 0:
        assert analysis.consistency.deviation_pct is None


@pytest.mark.parametrize(
    "energy,protein,carbs,fat,expected",
    [
        (52.2, 9.5, 58, 28, {"energy_kcal"}),
        (522, 95, 58, 28, {"protein_g"}),
        (522, 9.5, 580, 28, {"carbohydrate_g"}),
        (522, 9.5, 58, 2.8, {"total_fat_g"}),
        (292, 3, 7, 20, {"total_fat_g"}),
        (300, 20, 4000, 6.6666667, {"carbohydrate_g"}),
    ],
)
def test_single_field_ocr_hypotheses_do_not_rewrite_values(
    make_extraction, energy, protein, carbs, fat, expected
):
    extraction = label(make_extraction, energy, protein, carbs, fat)
    before = extraction.model_dump_json()
    analysis = analyze_nutrition(extraction)
    assert set(analysis.consistency.suspect_keys) == expected
    assert analysis.per_100["energy_kcal"] == energy
    assert analysis.per_100["carbohydrate_g"] == carbs
    assert extraction.model_dump_json() == before


@pytest.mark.parametrize(
    "number,expected",
    [
        (108, {10.8, 1.08, 0.108, 708, 188, 100}),
        (65, {56, 55, 66}),
        (77, {17, 71}),
        (0, {8}),
    ],
)
def test_correction_candidate_families(number, expected):
    # 65 -> 56 requires two substitutions, which must not be offered.
    if number == 65:
        expected = {55, 66}
        assert 56 not in correction_candidates(number)
    assert expected <= set(correction_candidates(number))


def test_unexplainable_mismatch_marks_all_core_values(make_extraction):
    analysis = analyze_nutrition(
        label(make_extraction, energy=999, protein=3.2, carbs=4.3, fat=5.4)
    )
    assert set(analysis.consistency.suspect_keys) == {
        "energy_kcal",
        "protein_g",
        "carbohydrate_g",
        "total_fat_g",
    }


def test_multiple_plausible_fields_are_all_suspect(make_extraction):
    analysis = analyze_nutrition(
        label(make_extraction, energy=410, protein=10, carbs=10, fat=10)
    )
    assert {"protein_g", "carbohydrate_g"} <= set(analysis.consistency.suspect_keys)


@pytest.mark.parametrize(
    "part,whole,amount",
    [
        ("total_sugars_g", "carbohydrate_g", 59),
        ("saturated_fat_g", "total_fat_g", 29),
        ("added_sugars_g", "total_sugars_g", 39),
    ],
)
def test_sanity_checks_mark_both_sides(make_extraction, part, whole, amount):
    extraction = label(make_extraction)
    if whole == "total_sugars_g":
        add(extraction, whole, 38)
    add(extraction, part, amount)
    check = analyze_nutrition(extraction).consistency
    assert check.status == "inconsistent"
    assert {part, whole} <= set(check.suspect_keys)


@pytest.mark.parametrize(
    "serving_amount,suspect",
    [
        (25.52, False),
        (23.2, False),
        (20.88, False),
        (25.53, True),
        (20.87, True),
        (0, True),
    ],
)
def test_cross_basis_ten_percent_tolerance(make_extraction, serving_amount, suspect):
    extraction = label(make_extraction)
    extraction.nutrition.serving_size = 40
    extraction.nutrition.serving_unit = "g"
    add(extraction, "carbohydrate_g", serving_amount, basis="per_serving")
    assert (
        "carbohydrate_g" in analyze_nutrition(extraction).consistency.suspect_keys
    ) == suspect


def test_partial_macros_still_run_sanity_checks(make_extraction):
    extraction = label(make_extraction)
    extraction.nutrition.rows.pop(0)
    add(extraction, "saturated_fat_g", 30)
    check = analyze_nutrition(extraction).consistency
    assert check.status == "insufficient_data"
    assert {"saturated_fat_g", "total_fat_g"} <= set(check.suspect_keys)


@pytest.mark.parametrize(
    "includes_fibre,energy,computed", [(False, 378, 378), (True, 338, 338)]
)
def test_polyols_and_explicit_fibre_convention(
    make_extraction, includes_fibre, energy, computed
):
    extraction = label(make_extraction, energy, 10, 50, 10)
    if includes_fibre:
        extraction.nutrition.rows[
            2
        ].raw_label = "Carbohydrate (including dietary fibre)"
    add(extraction, "other", 20, raw_label="Polyols")
    add(extraction, "fibre_g", 10)
    analysis = analyze_nutrition(extraction)
    assert analysis.consistency.computed_kcal == computed
    assert analysis.consistency.status == "consistent"
    assert "polyols_g" not in analysis.per_100


def test_no_serving_size_can_still_check_macros_per_serving(make_extraction):
    analysis = analyze_nutrition(label(make_extraction, basis="per_serving"))
    assert analysis.consistency.status == "consistent"
    assert analysis.per_100 == {}


def test_kj_and_other_salt_row(make_extraction):
    extraction = label(make_extraction)
    extraction.nutrition.rows[0].values[0].amount = 2184.048
    extraction.nutrition.rows[0].values[0].unit = "kJ"
    add(extraction, "other", 1.5, raw_label="Salt")
    analysis = analyze_nutrition(extraction)
    assert analysis.per_100["energy_kcal"] == pytest.approx(522)
    assert analysis.per_100["sodium_mg"] == 600
    assert analysis.consistency.status == "consistent"


def test_pack_only_values_can_be_normalized(make_extraction):
    extraction = label(make_extraction, basis="per_pack")
    extraction.nutrition.pack_size = 200
    extraction.nutrition.pack_unit = "g"
    analysis = analyze_nutrition(extraction)
    assert analysis.per_100["energy_kcal"] == 261
    assert analysis.per_pack["energy_kcal"] == 522


def test_servings_are_derived_from_compatible_pack_and_serving_sizes(make_extraction):
    extraction = label(make_extraction)
    extraction.nutrition.serving_size = 40
    extraction.nutrition.serving_unit = "g"
    extraction.nutrition.pack_size = 120
    extraction.nutrition.pack_unit = "g"
    analysis = analyze_nutrition(extraction)
    assert analysis.servings_per_pack == 3
    assert analysis.per_pack["energy_kcal"] == pytest.approx(626.4)
    assert "nutrition.serving_small" in analysis.notes


def test_volume_and_mass_never_cross_convert(make_extraction):
    extraction = label(make_extraction, basis="per_100ml")
    extraction.nutrition.serving_size = 40
    extraction.nutrition.serving_unit = "g"
    analysis = analyze_nutrition(extraction)
    assert analysis.per_100_unit == "ml"
    assert value_at_basis(extraction.nutrition, "energy_kcal", "per_serving") is None


def test_duplicate_conflict_marks_key_suspect(make_extraction):
    extraction = label(make_extraction)
    add(extraction, "total_sugars_g", 38)
    add(extraction, "total_sugars_g", 83)
    add(extraction, "total_sugars_g", 38)
    analysis = analyze_nutrition(extraction)
    assert "total_sugars_g" not in analysis.per_100
    assert "total_sugars_g" in analysis.consistency.suspect_keys
