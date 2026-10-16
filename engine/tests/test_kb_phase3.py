"""Independently identified cases, not observations from an unavailable real corpus."""

from pathlib import Path
import pytest
from engine import explain_term
from engine.kb_loader import TERMS
from engine.kb_review import needs_review, render_review
from engine.matcher import match_text


def test_phase3_count_and_complete_review_inventory():
    assert len(TERMS) >= 250
    review = render_review()
    assert Path("engine/KB_REVIEW.md").read_text(encoding="utf-8") == review
    for term in TERMS:
        if needs_review(term):
            assert f"| `{term.id}` | {term.confidence} |" in review
        for alias in term.names.hi + term.names.te:
            assert alias in review


@pytest.mark.parametrize(
    "text,categories",
    [
        ("cream cheese", {"milk", "dairy"}),
        ("ricotta", {"milk", "dairy"}),
        ("mascarpone", {"milk", "dairy"}),
        ("whole egg powder", {"egg", "egg_derived"}),
        ("dried egg white", {"egg", "egg_derived"}),
        ("egg yolk powder", {"egg", "egg_derived"}),
        ("pistachio paste", {"tree_nut"}),
        ("walnut oil", {"tree_nut"}),
        ("मक्खन", {"milk", "dairy"}),
        ("मूँगफली", {"peanut"}),
        ("గోధుమ పిండి", {"wheat", "gluten"}),
        ("రవ్వ", {"wheat", "gluten"}),
        ("వేరుశెనగపప్పు", {"peanut"}),
        ("బాదం", {"tree_nut"}),
        ("జీడిపప్పు", {"tree_nut"}),
        ("పెరుగు", {"milk", "dairy"}),
        ("నెయ్యి", {"milk", "dairy"}),
        ("మజ్జిగ", {"milk", "dairy"}),
        ("పంచదార", {"added_sugar"}),
        ("బెల్లం", {"added_sugar", "sugar_alias"}),
        ("అల్లం", {"root_vegetable"}),
        ("గుడ్లు", {"egg", "egg_derived"}),
        ("చేపలు", {"fish", "fish_derived"}),
        ("బియ్యపు రవ్వ", set()),
        ("corn semolina", set()),
        ("puffed rice", set()),
        ("pumpkin seeds", set()),
        ("పుదీనా", set()),
        ("వాము", set()),
    ],
)
def test_new_terms_and_regional_names(text, categories):
    result = match_text(text)
    assert {
        category for hit in result.matches for category in hit.categories
    } == categories
    assert result.matches and not result.unresolved


@pytest.mark.parametrize("text", ["दूधिया", "ादूध", "పాలుక", "ాపాలు"])
def test_indic_combining_marks_are_word_content(text):
    # A milk alias must not match inside another word or start after a vowel sign.
    assert not match_text(text).matches


@pytest.mark.parametrize("text", ["दूध", "పాలు", "[పాలు]", "(दूध)"])
def test_indic_whole_words_still_match(text):
    assert {
        category for hit in match_text(text).matches for category in hit.categories
    } == {"milk", "dairy"}


def test_generic_albumin_is_possible_explicit_egg_remains_definite():
    generic = match_text("albumin")
    assert not generic.matches[0].categories
    assert set(generic.matches[0].possible_categories) == {"egg", "egg_derived"}
    assert explain_term("albumin").caution
    for name in ("ovalbumin", "egg albumen"):
        assert set(match_text(name).matches[0].categories) == {"egg", "egg_derived"}


@pytest.mark.parametrize(
    "text,profile,state",
    [
        ("albumin", "egg", "possible"),
        ("ovalbumin", "egg", "conflict"),
        ("egg albumen", "egg", "conflict"),
        ("పెరుగు", "milk", "conflict"),
        ("వేరుశెనగపప్పు", "peanut", "conflict"),
        ("బియ్యపు రవ్వ", "gluten", "not_listed"),
        ("corn semolina", "gluten", "not_listed"),
        ("hydrolysed vegetable protein", "soy", "possible"),
        ("modified starch", "gluten", "possible"),
        ("दूधिया", "milk", "not_listed"),
    ],
)
def test_phase3_engine_regressions(make_extraction, make_profile, text, profile, state):
    from engine import evaluate

    output = evaluate(make_extraction(text), [make_profile(profile)])
    assert output.reports[0].results[0].state == state


@pytest.mark.parametrize(
    "text", ["lactitol", "maltodextrin", "date paste", "ghee", "walnut oil"]
)
def test_taxonomy_and_processing_review_is_visible_in_explain(text):
    assert explain_term(text).caution


@pytest.mark.parametrize(
    "text,possible",
    [
        ("modified starch", {"wheat", "gluten", "root_vegetable"}),
        ("hydrolysed vegetable protein", {"soy", "wheat", "gluten"}),
    ],
)
def test_unspecified_source_does_not_create_definite_conflict(text, possible):
    result = match_text(text)
    assert not {category for hit in result.matches for category in hit.categories}
    assert {
        category for hit in result.matches for category in hit.possible_categories
    } == possible
