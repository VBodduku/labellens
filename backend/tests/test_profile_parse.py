"""/api/profile/parse: 10 example sentences with recorded-style model answers (FakeLLM)."""
from __future__ import annotations

import asyncio
import json

import pytest

from backend.app.llm.base import ProviderUnavailableError
from backend.app.llm.router import LLMRouter
from backend.app.pipeline.profile_parse import BASIC_PARSING_WARNING, parse_profiles
from backend.tests.fakes import FakeLLM
from shared.contract import ProfileParseResponse


def person(name: str, *restrictions: tuple[str, str | None, str]) -> dict:
    return {"name": name, "restrictions": [{"key": k, "severity": s, "source_text": t} for k, s, t in restrictions]}


def parse(text: str, answer: dict | None, lang: str = "en") -> ProfileParseResponse:
    llm = FakeLLM([json.dumps(answer)] if answer is not None else [ProviderUnavailableError("down")])
    return asyncio.run(parse_profiles(text, lang, LLMRouter([llm], 5)))  # type: ignore[arg-type]


def summary(response: ProfileParseResponse) -> list[tuple[str, list[tuple[str, str]]]]:
    return [(p.name, [(r.key, r.severity) for r in p.restrictions]) for p in response.profiles]


CASES = [
    ("My son is allergic to peanuts and I'm Jain", "en",
     {"people": [person("Son", ("peanut", "strict", "allergic to peanuts")), person("Me", ("jain", "strict", "I'm Jain"))],
      "unparsed": []},
     [("Son", [("peanut", "strict")]), ("Me", [("jain", "strict")])]),
    ("mera beta peanuts se allergic hai", "hi",
     {"people": [person("Son", ("peanut", None, "peanuts se allergic"))], "unparsed": []},
     [("Son", [("peanut", "strict")])]),
    ("मेरे पिताजी को शुगर है और बीपी भी", "hi",
     {"people": [person("Father", ("diabetes_sugar", "strict", "शुगर"), ("low_sodium", "strict", "बीपी"))], "unparsed": []},
     [("Father", [("diabetes_sugar", "strict"), ("low_sodium", "strict")])]),
    ("నాకు నువ్వుల అలెర్జీ ఉంది", "te",
     {"people": [person("Me", ("sesame", "preference", "నువ్వుల అలెర్జీ"))], "unparsed": []},
     [("Me", [("sesame", "strict")])]),                                  # wording says allergy -> strict
    ("Aarav has a tree nut allergy, Thatha is diabetic", "en",
     {"people": [person("Aarav", ("tree_nut", "strict", "tree nut allergy")),
                 person("Thatha", ("diabetes_sugar", "strict", "diabetic"))], "unparsed": []},
     [("Aarav", [("tree_nut", "strict")]), ("Thatha", [("diabetes_sugar", "strict")])]),
    ("I'm trying to cut down on palm oil", "en",
     {"people": [person("Me", ("palm_oil", "strict", "trying to cut down on palm oil"))], "unparsed": []},
     [("Me", [("palm_oil", "preference")])]),                            # wording says preference
    ("My wife avoids onion and garlic", "en",
     {"people": [person("Wife", ("no_onion_garlic", None, "avoids onion and garlic"))], "unparsed": []},
     [("Wife", [("no_onion_garlic", "preference")])]),
    ("Grandma has kidney disease and is vegetarian", "en",
     {"people": [person("Grandmother", ("kidney_diet", "strict", "kidney disease"),
                        ("vegetarian", None, "is vegetarian"))], "unparsed": []},
     [("Grandmother", [("vegetarian", "strict")])]),                     # invalid key -> unparsed
    ("No idea, just checking", "en", {"people": [], "unparsed": ["just checking"]}, []),
    ("My daughter is lactose intolerant and vegan", "en",
     {"people": [person("Daughter", ("lactose", None, "lactose intolerant"), ("vegan", None, "vegan"),
                        ("lactose", None, "lactose intolerant"))], "unparsed": []},
     [("Daughter", [("lactose", "preference"), ("vegan", "strict")])]),  # intolerance: catalog default; dup collapsed
]


@pytest.mark.parametrize("text, lang, answer, expected", CASES, ids=[c[0][:30] for c in CASES])
def test_parse_examples(text: str, lang: str, answer: dict, expected: list) -> None:
    response = parse(text, answer, lang)
    assert summary(response) == expected
    assert response.needs_confirmation is True
    for profile in response.profiles:
        assert profile.profile_id.startswith("p_")
        for r in profile.restrictions:
            assert r.id.startswith("r_") and r.label and r.source_text


def test_invalid_key_lands_in_unparsed_and_thresholds_come_from_catalog() -> None:
    grandma = parse(CASES[7][0], CASES[7][2])
    assert grandma.unparsed == ["kidney disease"]
    father = parse(CASES[2][0], CASES[2][2], "hi")
    thresholds = {r.key: r.threshold for r in father.profiles[0].restrictions}
    assert thresholds["diabetes_sugar"] is not None and thresholds["diabetes_sugar"].nutrient == "total_sugars_g"
    assert thresholds["low_sodium"] is not None and thresholds["low_sodium"].nutrient == "sodium_mg"
    assert father.profiles[0].restrictions[0].kind == "health_limit"


@pytest.mark.parametrize("text, expected", [
    ("I am allergic to peanuts and I'm Jain", [("peanut", "strict"), ("jain", "strict")]),
    ("मुझे दूध से एलर्जी है", [("milk", "strict")]),
    ("నాకు షుగర్ ఉంది", [("diabetes_sugar", "strict")]),
])
def test_without_llm_keyword_parsing_makes_one_profile(text: str, expected: list) -> None:
    response = parse(text, None)
    assert [(r.key, r.severity) for r in response.profiles[0].restrictions] == expected
    assert response.profiles[0].name == "Me"
    assert BASIC_PARSING_WARNING in response.warnings and response.needs_confirmation


def test_without_llm_nothing_recognised_is_unparsed() -> None:
    response = parse("hello there", None)
    assert response.profiles == [] and response.unparsed == ["hello there"]


def test_need_the_model_dropped_is_flagged_for_confirmation() -> None:
    answer = {"people": [person("Son", ("peanut", "strict", "allergic to peanuts"))], "unparsed": []}
    response = parse("My son is allergic to peanuts and I am Jain", answer)
    assert summary(response) == [("Son", [("peanut", "strict")])]
    assert response.warnings == ["Also mentioned: Jain. Add it to the right person if it applies."]
