import pytest
from shared.contract import Ingredient
from engine.matcher import annotation, match_ingredients, match_text


@pytest.mark.parametrize("text,expected,forbidden", [
    ("coconut", set(), {"tree_nut"}), ("coconut milk", set(), {"milk", "dairy"}),
    ("coconut cream", set(), {"milk", "dairy"}), ("cocoa butter", set(), {"milk", "dairy"}),
    ("cacao butter", set(), {"milk"}), ("peanut butter", {"peanut"}, {"milk", "dairy"}),
    ("milk chocolate", {"milk", "dairy"}, set()),
    ("edible vegetable oil (palm)", {"palm_oil"}, set()),
    ("Emulsifier (INS 322 [Soy])", {"soy"}, {"egg"}),
    ("INS 322 (from sunflower)", set(), {"soy", "egg"}),
    ("INS 471 (vegetable origin)", set(), {"animal_derived"}),
    ("INS 471 (animal source)", {"animal_derived"}, set()),
    ("INS 631 (microbial origin)", set(), {"animal_derived", "fish_derived"}),
    ("Emulsifiers (471, 472e)", set(), set()),
    ("Chocolate (sugar, cocoa butter, milk solids)", {"added_sugar", "milk", "dairy"}, set()),
    ("onion & garlic powder", {"onion", "garlic"}, set()),
    ("dehydrated onion", {"onion"}, set()), ("garlic flakes", {"garlic"}, set()),
    ("dried ginger", set(), {"root_vegetable"}), ("fresh ginger", {"root_vegetable"}, set()),
    ("rice rava", set(), {"wheat", "gluten"}), ("rava", {"wheat", "gluten"}, set()),
    ("maida", {"wheat", "gluten"}, set()), ("atta", {"wheat", "gluten"}, set()),
    ("suji", {"wheat", "gluten"}, set()), ("durum wheat", {"wheat", "gluten"}, set()),
    ("jau", {"gluten"}, {"added_sugar"}), ("rye", {"gluten"}, set()),
    ("moongphali", {"peanut"}, set()), ("singdana", {"peanut"}, set()),
    ("मूंगफली", {"peanut"}, set()), ("వేరుశెనగ", {"peanut"}, set()),
    ("दूध", {"milk", "dairy"}, set()), ("పాలు", {"milk", "dairy"}, set()),
    ("khoya", {"milk", "dairy"}, set()), ("mawa", {"milk", "dairy"}, set()),
    ("malai", {"milk", "dairy"}, set()), ("ghee", {"milk", "dairy"}, set()),
    ("whey protein", {"milk", "dairy"}, set()), ("sodium caseinate", {"milk", "dairy"}, set()),
    ("lactic acid", set(), {"milk", "dairy"}),
    ("egg lecithin", {"egg", "egg_derived"}, {"soy"}),
    ("INS 1105", {"egg", "egg_derived"}, set()), ("E120", {"insect_derived"}, set()),
    ("INS 904", {"insect_derived"}, set()), ("INS 901", {"insect_derived"}, set()),
    ("INS 441", {"gelatin", "animal_derived"}, set()), ("INS 542", {"animal_derived"}, set()),
    ("INS 966", {"polyol", "milk", "dairy"}, set()),
    ("E950", {"artificial_sweetener"}, set()), ("INS 960", set(), {"artificial_sweetener"}),
    ("E621", {"added_msg"}, set()), ("E223", {"sulphite"}, set()),
    ("fish sauce", {"fish", "fish_derived"}, set()), ("jhinga", {"crustacean"}, set()),
    ("oysters", {"mollusc"}, set()), ("celery seed", {"celery"}, set()), ("lupin flour", {"lupin"}, set()),
    ("til", {"sesame"}, set()), ("sarson", {"mustard"}, set()),
    ("kaju", {"tree_nut"}, set()), ("badam", {"tree_nut"}, set()),
    ("pista", {"tree_nut"}, set()), ("akhrot", {"tree_nut"}, set()),
    ("maltodextrin", {"added_sugar", "sugar_alias"}, set()),
    ("invert syrup", {"added_sugar", "sugar_alias"}, set()),
    ("honey", {"honey", "added_sugar"}, set()),
    ("500(ii)", set(), {"milk"}), ("INS 500(ii)", set(), set()),
    ("pea nuts", {"peanut"}, {"milk"}), ("whey pow der", {"milk", "dairy"}, set()),
    ("whey powdr", {"milk", "dairy"}, set()),
    ("almond milk", {"tree_nut"}, {"milk", "dairy"}),
    ("almond butter", {"tree_nut"}, {"milk", "dairy"}),
    ("soy milk", {"soy"}, {"milk", "dairy"}),
    ("oat milk", set(), {"milk", "dairy"}),
    ("rice milk", set(), {"milk", "dairy"}),
    ("cream of tartar", set(), {"milk", "dairy"}),
    ("butter beans", set(), {"milk", "dairy"}),
    ("shea butter", set(), {"milk", "dairy"}),
    ("artificial butter flavour", set(), {"milk", "dairy"}),
])
def test_categories_and_compound_protection(text, expected, forbidden):
    result = match_text(text)
    categories = {category for hit in result.matches for category in hit.categories}
    assert expected <= categories
    assert not categories & forbidden
    assert result.matches, text
    assert not result.unresolved, (text, result.unresolved)


@pytest.mark.parametrize("text,expected", [
    ("INS 471", {"animal_derived"}), ("INS 627", {"animal_derived", "fish_derived"}),
    ("INS 322", {"soy", "egg", "egg_derived"}), ("oats", {"gluten"}),
    ("dried ginger", {"root_vegetable"}), ("turmeric", {"root_vegetable"}),
    ("spices and condiments", {"onion", "garlic"}),
    ("INS 322 (plant source)", {"soy"}),
])
def test_possible_categories(text, expected):
    result = match_text(text)
    assert {category for hit in result.matches for category in hit.possible_categories} == expected


@pytest.mark.parametrize("text", ["mystery xyz", "nut", "but", "creamery", "milkweed", "INS 999", "INS 472z", "INS 500(iv)"])
def test_unknown_and_non_words(text):
    result = match_text(text)
    assert not result.matches
    assert result.unresolved


def test_multiple_codes_are_independent():
    result = match_text("Emulsifiers (INS 471, INS 322 [Soy], INS 472e)")
    by_id = {hit.entry.id: hit for hit in result.matches}
    assert by_id['ins_471'].possible_categories == ('animal_derived',)
    assert by_id['ins_472e'].possible_categories == ('animal_derived',)
    assert by_id['ins_322'].categories == ('soy',)


def test_subingredients_and_unreadable():
    ingredients = [Ingredient(id='a', name='chocolate', raw_text='chocolate', sub_ingredients=[
        Ingredient(id='a_0', name='milk', raw_text='milk'),
        Ingredient(id='a_1', name='peanut', raw_text='peanut', readability='unreadable')])]
    records = match_ingredients(ingredients)
    assert [record.ingredient.id for record in records] == ['a', 'a_0', 'a_1']
    assert annotation(records[1]).categories == ['milk', 'dairy']
    assert not records[2].matches


def test_unknown_inside_partially_resolved_compound():
    result = match_text('Chocolate (sugar, zyx mystery)')
    assert any('added_sugar' in hit.categories for hit in result.matches)
    assert result.unresolved


@pytest.mark.parametrize('text,possible', [
    ('INS 471 (not vegetable origin)', {'animal_derived'}),
    ('INS 322 (not from sunflower)', {'soy','egg','egg_derived'}),
    ('INS 322 (not from soy)', {'soy','egg','egg_derived'}),
    ('INS 322 (soy free)', {'soy','egg','egg_derived'}),
])
def test_negated_source_does_not_become_affirmative_qualifier(text,possible):
    matched=match_text(text)
    assert not {category for hit in matched.matches for category in hit.categories}
    assert {category for hit in matched.matches for category in hit.possible_categories}==possible
