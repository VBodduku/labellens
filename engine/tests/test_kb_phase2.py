import pytest
from engine import explain_term
from engine.matcher import match_text


@pytest.mark.parametrize(
    "text,categories",
    [
        ("condensed milk", {"milk", "dairy"}),
        ("evaporated milk", {"milk", "dairy"}),
        ("milk permeate", {"milk", "dairy"}),
        ("whey permeate powder", {"milk", "dairy"}),
        ("cream powder", {"milk", "dairy"}),
        ("buttermilk powder", {"milk", "dairy"}),
        ("milk protein concentrate", {"milk", "dairy"}),
        ("shrikhand", {"milk", "dairy"}),
        ("wheat bran", {"wheat", "gluten"}),
        ("spelt", {"wheat", "gluten"}),
        ("seitan", {"wheat", "gluten"}),
        ("couscous", {"wheat", "gluten"}),
        ("malted barley flour", {"gluten"}),
        ("almond flour", {"tree_nut"}),
        ("peanut flour", {"peanut"}),
        ("sesame meal", {"sesame"}),
        ("mustard powder", {"mustard"}),
        ("soy protein concentrate", {"soy"}),
        ("fish oil", {"fish", "fish_derived"}),
        ("fish gelatin", {"fish", "fish_derived", "gelatin"}),
        ("duck meat", {"poultry"}),
        ("chicken fat", {"poultry", "animal_derived"}),
        ("rice syrup", {"added_sugar", "sugar_alias"}),
        ("maple syrup", {"added_sugar", "sugar_alias"}),
        ("molasses", {"added_sugar", "sugar_alias"}),
        ("muscovado sugar", {"added_sugar", "sugar_alias"}),
        ("palm sugar", {"added_sugar", "sugar_alias"}),
        ("besan", set()),
        ("buckwheat", set()),
        ("green gram", set()),
        ("nutmeg", set()),
        ("finger millet", set()),
    ],
)
def test_phase_two_ingredient_coverage(text, categories):
    result = match_text(text)
    assert {c for match in result.matches for c in match.categories} == categories
    assert not result.unresolved


def test_expanded_compounds_do_not_inherit_shorter_alias_categories():
    assert not any(
        "palm_oil" in match.categories for match in match_text("palm sugar").matches
    )
    assert not any(
        "wheat" in match.categories for match in match_text("buckwheat").matches
    )


def test_soy_sauce_does_not_assert_wheat_without_a_component_list():
    result = match_text("soy sauce")
    assert {c for match in result.matches for c in match.categories} == {"soy"}
    assert {c for match in result.matches for c in match.possible_categories} == {
        "wheat",
        "gluten",
    }
    assert explain_term("soy sauce").caution


@pytest.mark.parametrize(
    "term,lang,display",
    [
        ("chickpea", "hi", "बेसन"),
        ("finger millet", "te", "రాగులు"),
        ("pigeon peas", "te", "కందులు"),
    ],
)
def test_new_indian_display_names(term, lang, display):
    assert explain_term(term, lang).display_name == display
