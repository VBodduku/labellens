import pytest
from engine.normalize import extract_codes, normalize, qualifiers, split_top_level


@pytest.mark.parametrize("text,expected", [
    ("INS 322", ("322",)), ("E322", ("322",)), ("E 322", ("322",)),
    ("322(i)", ("322(i)",)), ("500(ii)", ("500(ii)",)),
    ("INS 471, 472e", ("471", "472e")),
    ("Emulsifiers (471, 472e)", ("471", "472e")),
    ("INS 322(i), INS 500(ii)", ("322(i)", "500(ii)")),
    ("Emulsifier [INS 322 [Soy]]", ("322",)),
    ("INS 322, INS 322", ("322",)), ("E-472e", ("472e",)),
    ("Sugar 500 g", ()), ("Sugar 120%", ()), ("Batch 2026", ()),
    ("Vitamin E", ()), ("120.5 g", ()), ("E3220x", ()),
])
def test_codes(text, expected):
    assert extract_codes(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("  MILK [12%] ", "milk"), ("Peanuts (22%)", "peanuts"),
    ("Whey  10 mg", "whey"), ("ＣＡＳＥＩＮ", "casein"),
    ("मूंगफली", "मूंगफली"), ("వేరుశెనగ", "వేరుశెనగ"),
    ("onion & garlic powder", "onion garlic powder"),
])
def test_normalize(text, expected):
    assert normalize(text) == expected


def test_nested_qualifiers():
    assert qualifiers("Emulsifier (INS 322 [Soy])") == ("soy", "ins 322 (soy)")


def test_split_nested():
    assert split_top_level("Sugar, Chocolate (milk, cocoa butter), salt") == ("Sugar", "Chocolate (milk, cocoa butter)", "salt")
