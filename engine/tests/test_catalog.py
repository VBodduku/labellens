import engine
from shared.contract import CATEGORIES,RestrictionCatalogItem


def test_public_api_and_copy_isolation():
    assert set(engine.__all__)=={'evaluate','analyze_nutrition','explain_term','restriction_catalog','category_vocabulary'}
    catalog=engine.restriction_catalog()
    assert all(type(item) is RestrictionCatalogItem for item in catalog)
    catalog[0].categories.clear()
    catalog[0].key='changed'
    assert engine.restriction_catalog()[0].key=='peanut'
    assert engine.restriction_catalog()[0].categories==['peanut']
    vocabulary=engine.category_vocabulary()
    vocabulary.clear()
    assert engine.category_vocabulary()==CATEGORIES


def test_explanations(make_extraction):
    assert engine.explain_term('whey').origin=='animal'
    assert engine.explain_term('INS 471').caution
    assert engine.explain_term('INS 322 [Soy]').categories==['soy']
    assert engine.explain_term('milk','hi').display_name=='दूध'
    assert engine.explain_term('whey','te').display_name=='whey'
    assert engine.explain_term('zyx unknown') is None
    assert engine.analyze_nutrition(make_extraction('salt')) is None
