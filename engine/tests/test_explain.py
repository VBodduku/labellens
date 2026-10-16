import pytest
from shared.contract import ExplainResponse
from engine import explain_term


@pytest.mark.parametrize(
    "term,lang,id,origin,categories",
    [
        ("whey", "en", "whey", "animal", {"milk", "dairy"}),
        ("दूध", "hi", "milk", "animal", {"milk", "dairy"}),
        ("పాలు", "te", "milk", "animal", {"milk", "dairy"}),
        ("INS 322 [Soy]", "en", "ins_322", "plant", {"soy"}),
        ("INS 471 (vegetable origin)", "en", "ins_471", "plant", set()),
        ("cocoa butter", "te", "cocoa_butter", "plant", set()),
        ("turmeric", "hi", "turmeric", "varies", set()),
    ],
)
def test_explain_contract_localization_and_origin(term, lang, id, origin, categories):
    response = explain_term(term, lang)
    assert isinstance(response, ExplainResponse)
    assert (response.canonical_id, response.origin, response.source) == (
        id,
        origin,
        "kb",
    )
    assert set(response.categories) == categories
    assert response.description
    ExplainResponse.model_validate_json(response.model_dump_json())


def test_possible_categories_are_explicit_in_caution():
    assert "animal-derived" in explain_term("INS 471").caution
    assert "soy" in explain_term("INS 322").caution
    assert "Source resolved" in explain_term("INS 471 (vegetable origin)").caution


@pytest.mark.parametrize("term", ["completely unknown xyz", "whey, salt", "INS 999"])
def test_unknown_or_multi_term_explanation_delegates_to_backend(term):
    assert explain_term(term) is None
