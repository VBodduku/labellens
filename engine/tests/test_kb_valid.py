import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from shared.contract import ALLERGEN_CATEGORIES,CATEGORIES
from engine.kb_loader import CATALOG,TERMS,Term,validate_indexes


def test_kb_count_categories_and_aliases():
    validate_indexes()
    assert len(TERMS)>=200
    assert set(ALLERGEN_CATEGORIES)<={c for t in TERMS for c in t.categories+t.possible_categories}
    assert all(set(t.categories+t.possible_categories)<=set(CATEGORIES) for t in TERMS)
    assert all(t.notes and (t.origin=='varies' or not t.possible_categories) for t in TERMS)
    assert all(t.notes and t.confidence=='medium' for t in TERMS if t.possible_categories)


@pytest.mark.parametrize('change',[{'categories':['fictional']},{'possible_categories':['animal_derived'],'origin':'plant'},{'notes':''},{'ins':['E999']},{'confidence':'low'},{'unexpected':1}])
def test_term_model_rejects_bad_data(change):
    data=TERMS[0].model_dump()
    data.update(change)
    with pytest.raises(ValidationError):
        Term.model_validate(data)


def test_catalog_contains_all_frozen_keys():
    path=Path(__file__).resolve().parents[2]/'shared/fixtures/catalog.json'
    fixture=json.loads(path.read_text(encoding='utf-8'))
    actual={c.key:c for c in CATALOG}
    for item in fixture:
        assert actual[item['key']].model_dump()==item


@pytest.mark.parametrize('code',['220','221','222','223','224','225','226','227','228','471','472a','472b','472c','472d','472e','472f','627','631','635','920','1105','966','120','441','904','901','542'])
def test_priority_codes_present(code):
    assert code in {code for term in TERMS for code in term.ins}
