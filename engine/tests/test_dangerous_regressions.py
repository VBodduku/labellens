"""Adversarial regressions discovered in review, not observations from real packets."""

import pytest

from engine import evaluate
from engine.matcher import match_text
from engine.normalize import split_top_level


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ﬃbre,Peanuts", ("ﬃbre", "Peanuts")),
        ("ﬄour;Milk", ("ﬄour", "Milk")),
        ("İNGREDIENT,MILK", ("İNGREDIENT", "MILK")),
        ("ﬃbre，Peanuts", ("ﬃbre", "Peanuts")),
        ("ﬃbre［Milk，Sugar］；Peanuts", ("ﬃbre［Milk，Sugar］", "Peanuts")),
    ],
)
def test_list_splitting_preserves_original_offsets_and_text(text, expected):
    assert split_top_level(text) == expected


@pytest.mark.parametrize(
    "text,key,category",
    [
        ("ﬃbre,Peanuts", "peanut", "peanut"),
        ("ﬄour,Milk", "milk", "milk"),
        ("İNGREDIENT,MILK", "milk", "milk"),
        ("ﬃbre，Peanuts", "peanut", "peanut"),
        ("acetic acid esters of mono and diglyceride egg", "egg", "egg"),
        (
            "mixed acetic and tartaric acid esters of mono and diglyceride egg",
            "egg",
            "egg",
        ),
    ],
)
def test_explicit_allergen_cannot_be_lost_by_normalization_or_fuzzy_match(
    make_extraction, make_profile, text, key, category
):
    matched = match_text(text)
    assert category in {c for hit in matched.matches for c in hit.categories}
    output = evaluate(make_extraction(text), [make_profile(key)])
    result = output.reports[0].results[0]
    assert (result.state, result.reason_code) == ("conflict", "CONFLICT_INGREDIENT")
    assert result.evidence[0].text == text  # Exact label text remains untouched.


@pytest.mark.parametrize(
    "text,expected_id,forbidden",
    [
        ("co coa butter", "cocoa_butter", {"milk", "dairy"}),
        ("cocoa but ter", "cocoa_butter", {"milk", "dairy"}),
        ("buck wheat", "buckwheat", {"wheat", "gluten"}),
    ],
)
def test_fuzzy_compound_protection_still_repairs_inserted_spaces(
    text, expected_id, forbidden
):
    result = match_text(text)
    assert expected_id in {hit.entry.id for hit in result.matches}
    assert not {c for hit in result.matches for c in hit.categories} & forbidden
