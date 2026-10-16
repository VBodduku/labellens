"""Feature-freeze boundaries: accepted contract objects must evaluate without crashing."""

import math
import sys

import pytest
from engine import evaluate, restriction_catalog
from shared.contract import (
    Evidence,
    Ingredient,
    NutritionTable,
    NutrientRow,
    NutrientValue,
    Profile,
)
from shared.engine_interface import EngineOutput


def checked(extraction, profiles):
    before = extraction.model_dump_json()
    result = evaluate(extraction, profiles)
    EngineOutput.model_validate_json(result.model_dump_json())
    assert extraction.model_dump_json() == before
    return result


@pytest.mark.parametrize(
    "presence,complete,expected",
    [
        ("not_found", False, "UNKNOWN_SECTION_MISSING"),
        ("partial", False, "UNKNOWN_TRUNCATED"),
        ("found", True, "NOT_LISTED_COMPLETE"),
    ],
)
def test_empty_extraction(make_extraction, make_profile, presence, complete, expected):
    output = checked(
        make_extraction(presence=presence, complete=complete), [make_profile()]
    )
    assert output.reports[0].results[0].reason_code == expected
    assert not output.annotations


def test_no_profiles_still_returns_extraction_analysis(make_extraction):
    output = checked(make_extraction("milk"), [])
    assert output.reports == []
    assert output.annotations[0].categories == ["milk", "dairy"]


def test_profile_without_restrictions_has_no_checks(make_extraction):
    output = checked(
        make_extraction("milk"),
        [Profile(profile_id="empty", name="Empty", restrictions=[])],
    )
    assert output.reports[0].results == []
    assert (
        output.reports[0].overall == "not_listed"
    )  # Existing empty aggregation identity.


@pytest.mark.parametrize("parent_readability", ["clear", "partial", "unreadable"])
def test_ingredient_with_only_subingredients_preserves_positive_signal(
    make_extraction, make_profile, parent_readability
):
    extraction = make_extraction()
    extraction.ingredients = [
        Ingredient(
            id="parent",
            name="",
            raw_text="",
            readability=parent_readability,
            sub_ingredients=[
                Ingredient(
                    id="child",
                    name="peanut",
                    raw_text="Peanut",
                    evidence=[
                        Evidence(image_id="img_1", text="Peanut", status="verified")
                    ],
                )
            ],
        )
    ]
    output = checked(extraction, [make_profile()])
    result = output.reports[0].results[0]
    assert result.state == "conflict"
    assert any(match.ingredient_id == "child" for match in result.matches)
    assert result.evidence[0].image_id == "img_1"


@pytest.mark.parametrize("same_id", [False, True])
def test_duplicate_multi_panel_ingredients_preserve_both_locations(
    make_extraction, make_profile, same_id
):
    extraction = make_extraction("peanut", "peanut")
    for index, item in enumerate(extraction.ingredients):
        item.evidence[0].image_id = f"img_{index}"
    if same_id:
        extraction.ingredients[1].id = extraction.ingredients[0].id
    output = checked(extraction, [make_profile()])
    result = output.reports[0].results[0]
    assert result.state == "conflict"
    assert {e.image_id for e in result.evidence} == {"img_0", "img_1"}
    assert len(output.annotations) == 2  # Panel merging belongs to Part 2.


@pytest.mark.parametrize(
    "key,unit",
    [
        ("energy_kcal", "kcal"),
        ("sodium_mg", "g"),
        ("protein_g", "g"),
        ("total_sugars_g", "g"),
        ("other", "unknown"),
    ],
)
@pytest.mark.parametrize(
    "amount",
    [None, -1.0, 0.0, 1e-320, 1e200, sys.float_info.max, math.nan, math.inf, -math.inf],
)
def test_absurd_nutrient_values_do_not_raise(
    make_extraction, make_profile, key, unit, amount
):
    extraction = make_extraction("salt")
    extraction.nutrition = NutritionTable(
        serving_size=1e-320,
        serving_unit="g",
        pack_size=sys.float_info.max,
        pack_unit="g",
        rows=[
            NutrientRow(
                key=key,
                raw_label=key,
                values=[
                    NutrientValue(
                        basis="per_serving",
                        amount=amount,
                        unit=unit,
                        raw_text=str(amount),
                    )
                ],
            )
        ],
    )
    output = checked(extraction, [make_profile("low_sodium")])
    assert output.nutrition_analysis is not None
    assert all(
        math.isfinite(value) for value in output.nutrition_analysis.per_100.values()
    )
    assert all(
        math.isfinite(value) for value in output.nutrition_analysis.per_pack.values()
    )
    if amount is None or amount < 0 or not math.isfinite(amount):
        assert not output.nutrition_analysis.per_100


@pytest.mark.parametrize(
    "key", ["", "not_a_catalog_key", "低糖", "milk\x00", "__class__"]
)
def test_unknown_restriction_keys_are_undeterminable(
    make_extraction, make_profile, key
):
    output = checked(make_extraction("peanut"), [make_profile(key)])
    result = output.reports[0].results[0]
    assert (result.state, result.unknown_kind, result.reason_code) == (
        "unknown",
        "undeterminable",
        "UNKNOWN_NOT_ON_LABELS",
    )


def test_every_catalog_restriction_handles_empty_sections(
    make_extraction, make_profile
):
    profiles = [make_profile(item.key) for item in restriction_catalog()]
    output = checked(make_extraction(presence="not_found", complete=False), profiles)
    assert all(
        result.state == "unknown"
        for report in output.reports
        for result in report.results
    )
