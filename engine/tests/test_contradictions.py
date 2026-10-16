"""Unrecognised ingredients, user confirmations and contradictions (evidence-grounded comparison)."""
from __future__ import annotations

import engine
from shared.contract import (
    AllergenStatement,
    Claim,
    Evidence,
    NutrientRow,
    NutrientValue,
    NutritionTable,
    SectionStatus,
)
from shared.engine_interface import TermInterpretation


def only(extraction, profile, interpretations=None):
    output = engine.evaluate(extraction, [profile], interpretations)
    return output.reports[0].results[0], output


# ------------------------------------------------------------------------------- unrecognised words
def test_an_unrecognised_ingredient_blocks_not_listed(make_extraction, make_profile):
    result, _ = only(make_extraction("salt", "zorbex paste"), make_profile("peanut"))
    assert (result.state, result.unknown_kind, result.reason_code) == ("unknown", "undeterminable", "UNKNOWN_UNRESOLVED_TERM")
    assert result.message_params["term"] == "zorbex paste"
    assert result.evidence[0].text == "zorbex paste"


def test_an_ai_interpretation_with_no_relevant_category_resolves_it(make_extraction, make_profile):
    neutral = TermInterpretation(term="zorbex paste", categories=[], origin="plant", confidence=0.9, rationale="A fruit paste")
    result, _ = only(make_extraction("salt", "zorbex paste"), make_profile("peanut"), {"zorbex paste": neutral})
    assert (result.state, result.reason_code) == ("not_listed", "NOT_LISTED_COMPLETE")


def test_leftover_words_of_a_matched_ingredient_do_not_block(make_extraction, make_profile):
    result, _ = only(make_extraction("salt", "oats flour"), make_profile("peanut"))
    assert result.state == "not_listed"


def test_an_unknown_word_does_not_touch_threshold_only_checks(make_extraction, make_profile):
    extraction = make_extraction("zorbex paste")
    result, _ = only(extraction, make_profile("low_sodium"))
    assert result.reason_code != "UNKNOWN_UNRESOLVED_TERM"


# ------------------------------------------------------------------------------- confirmations
def confirmed(extraction, index, **categories):
    extraction.ingredients[index].confirmations = dict(categories)
    return extraction


def test_confirming_an_ambiguous_source_absent_says_who_checked(make_extraction, make_profile):
    before, _ = only(make_extraction("salt", "INS 471"), make_profile("vegetarian"))
    assert before.reason_code == "POSSIBLE_AMBIGUOUS_SOURCE"
    after, _ = only(confirmed(make_extraction("salt", "INS 471"), 1, animal_derived="absent"), make_profile("vegetarian"))
    assert (after.state, after.reason_code) == ("not_listed", "NOT_LISTED_USER_CONFIRMED")
    assert after.matches[0].note == "Confirmed by you on the pack."


def test_confirming_an_ambiguous_source_present_is_a_conflict(make_extraction, make_profile):
    result, _ = only(confirmed(make_extraction("salt", "INS 471"), 1, animal_derived="present"), make_profile("vegetarian"))
    assert (result.state, result.reason_code) == ("conflict", "CONFLICT_USER_CONFIRMED")
    assert result.message_params == {"term": "INS 471", "category": "animal_derived"}


def test_an_ai_guess_confirmed_absent_drops_out(make_extraction, make_profile):
    guess = {"zorbex paste": TermInterpretation(term="zorbex paste", categories=["peanut"], confidence=0.9, rationale="Looks nutty")}
    assert only(make_extraction("zorbex paste"), make_profile("peanut"), guess)[0].reason_code == "POSSIBLE_LLM_INTERPRETATION"
    result, _ = only(confirmed(make_extraction("zorbex paste"), 0, peanut="absent"), make_profile("peanut"), guess)
    assert result.reason_code == "NOT_LISTED_USER_CONFIRMED"


def test_an_unknown_word_confirmed_absent_for_the_profile_lifts_the_block(make_extraction, make_profile):
    result, _ = only(confirmed(make_extraction("salt", "zorbex paste"), 1, peanut="absent"), make_profile("peanut"))
    assert result.reason_code == "NOT_LISTED_USER_CONFIRMED"


def test_a_confirmation_never_overrides_a_definite_kb_fact(make_extraction, make_profile):
    result, _ = only(confirmed(make_extraction("milk solids"), 0, milk="absent"), make_profile("milk"))
    assert (result.state, result.reason_code) == ("conflict", "CONFLICT_INGREDIENT")


# ------------------------------------------------------------------------------- contradictions
def test_a_green_mark_with_egg_is_a_contradiction_linked_to_both_sides(make_extraction, make_profile):
    extraction = make_extraction("salt", "egg powder", mark="veg")
    extraction.veg_mark.evidence = Evidence(image_id="img_0", text="Green vegetarian mark", status="approximate")
    result, output = only(extraction, make_profile("vegetarian"))
    [found] = output.contradictions
    assert (found.kind, found.message_key) == ("veg_mark", "contradiction.veg_mark")
    assert [e.text for e in found.evidence] == ["egg powder", "Green vegetarian mark"]
    assert found.field_path == "ingredients[1].name"
    assert [(r.profile_id, r.restriction_id) for r in found.affects] == [("p", "r")]
    assert result.state == "conflict"                                        # the stricter side stands


def test_free_from_versus_a_listed_ingredient(make_extraction, make_profile):
    extraction = make_extraction("refined wheat flour")
    extraction.allergen_statements = [AllergenStatement(id="a", type="free_from", raw_text="Gluten free", items=["gluten"])]
    result, output = only(extraction, make_profile("gluten"))
    assert [(c.kind, c.message_params) for c in output.contradictions] == [
        ("free_from", {"item": "gluten", "term": "refined wheat flour"})]
    assert result.state == "conflict"


def test_a_claim_versus_the_ingredients_and_the_nutrition_table(make_extraction, make_profile):
    extraction = make_extraction("water", "sugar")
    extraction.claims = [Claim(id="c", raw_text="No added sugar")]
    extraction.nutrition = NutritionTable(rows=[NutrientRow(key="added_sugars_g", raw_label="Added Sugars (g)", values=[
        NutrientValue(basis="per_100ml", amount=14.2, unit="g", raw_text="14.2")])])
    extraction.nutrition_section = SectionStatus(presence="found", complete=True)
    _, output = only(extraction, make_profile("peanut"))
    assert [(c.kind, c.message_params["term"]) for c in output.contradictions] == [
        ("claim", "sugar"), ("claim", "Added Sugars (g) 14.2")]
    assert output.contradictions[1].field_path == "nutrition.rows[0].values[0].amount"


def test_a_claim_the_label_bears_out_is_not_a_contradiction(make_extraction, make_profile):
    extraction = make_extraction("whole wheat flour", "rice bran oil")
    extraction.claims = [Claim(id="c", raw_text="100% Palm oil-free")]
    assert only(extraction, make_profile("peanut"))[1].contradictions == []


def test_ai_versus_print_and_photo_versus_photo_come_from_recorded_issues(make_extraction, make_profile):
    extraction = make_extraction("salt")
    extraction.nutrition = NutritionTable(rows=[
        NutrientRow(key="sodium_mg", raw_label="Sodium (mg)", values=[NutrientValue(basis="per_100g", amount=750.2, unit="mg", raw_text="750.2")]),
        NutrientRow(key="total_sugars_g", raw_label="Total Sugars", values=[NutrientValue(basis="per_100g", amount=1.8, unit="g", raw_text="1.8")]),
    ])
    extraction.nutrition_section = SectionStatus(presence="found", complete=True, issues=[
        "llm_ocr_number_mismatch:sodium_mg:per_100g:75.2", "panel_disagreement:total_sugars_g:per_100g:1.8:18.0", "llm_ocr_number_mismatch:energy_kcal"])
    _, output = only(extraction, make_profile("low_sodium"))
    assert [(c.kind, c.message_params) for c in output.contradictions] == [
        ("ai_vs_print", {"nutrient": "sodium_mg", "ai_value": 75.2, "value": 750.2}),
        ("panels", {"nutrient": "total_sugars_g", "value": 1.8, "other": 18.0}),
    ]
    assert output.contradictions[0].affects[0].restriction_id == "r"           # the sodium limit uses that value
    assert "Neither is used until you check the pack." in output.contradictions[0].explanation


def test_a_clean_label_has_no_contradictions(make_extraction, make_profile):
    assert only(make_extraction("salt", "sugar"), make_profile("peanut"))[1].contradictions == []


# ------------------------------------------------------------------------------- checked on the pack
def test_a_checked_key_survives_a_recheck_and_leaves_the_stricter_verdict(make_extraction, make_profile):
    extraction = make_extraction("salt", "egg powder", mark="veg")
    _, first = only(extraction, make_profile("vegetarian"))
    [found] = first.contradictions
    assert found.key == "veg_mark:category=egg_derived|term=egg powder" and not found.checked
    extraction.checked_contradictions = [found.key]
    result, again = only(extraction, make_profile("vegetarian"))
    assert again.contradictions[0].checked and again.contradictions[0].key == found.key
    assert result.state == "conflict"          # the pack lists egg: checking it does not soften the verdict


def test_confirming_the_printed_number_checks_it_and_lets_the_limit_use_it(make_extraction, make_profile):
    def label(confirmed: bool):
        extraction = make_extraction("salt")
        value = NutrientValue(basis="per_100g", amount=750.2, unit="mg", raw_text="750.2",
                              readability="clear" if confirmed else "partial", corrected_by_user=confirmed)
        extraction.nutrition = NutritionTable(rows=[NutrientRow(key="sodium_mg", raw_label="Sodium (mg)", values=[value])])
        extraction.nutrition_section = SectionStatus(presence="found", complete=True,
                                                     issues=["llm_ocr_number_mismatch:sodium_mg:per_100g:75.2"])
        return extraction

    before, open_output = only(label(confirmed=False), make_profile("low_sodium"))
    after, checked_output = only(label(confirmed=True), make_profile("low_sodium"))
    assert not open_output.contradictions[0].checked and before.state == "unknown"
    assert checked_output.contradictions[0].checked and after.state == "conflict"     # 750 mg is over the limit
