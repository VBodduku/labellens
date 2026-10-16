import pytest
import engine
from shared.contract import AllergenStatement, Evidence, Ingredient, NutritionTable, NutrientRow, NutrientValue
from shared.engine_interface import EngineOutput, TermInterpretation


def result(extraction, profile, interpretations=None):
    output = engine.evaluate(extraction, [profile], interpretations)
    EngineOutput.model_validate_json(output.model_dump_json())
    return output.reports[0].results[0]


@pytest.mark.parametrize('key,term,mark,state,code', [
    ('peanut','groundnut','not_found','conflict','CONFLICT_INGREDIENT'),
    ('milk','whey','not_found','conflict','CONFLICT_INGREDIENT'),
    ('vegetarian','INS 471','not_found','possible','POSSIBLE_AMBIGUOUS_SOURCE'),
    ('vegetarian','INS 471 (plant source)','not_found','not_listed','NOT_LISTED_COMPLETE'),
    ('vegetarian','INS 471','veg','not_listed','NOT_LISTED_VEG_MARK'),
    ('jain','natural flavours','veg','possible','POSSIBLE_AMBIGUOUS_SOURCE'),
    ('vegan','natural flavours','veg','possible','POSSIBLE_AMBIGUOUS_SOURCE'),
    ('vegetarian','egg','veg','conflict','CONFLICT_INGREDIENT'),
    ('vegetarian','INS 120','veg','conflict','CONFLICT_INGREDIENT'),
    ('vegan','milk','veg','conflict','CONFLICT_INGREDIENT'),
    ('jain','onion','veg','conflict','CONFLICT_INGREDIENT'),
    ('jain','turmeric','veg','possible','POSSIBLE_AMBIGUOUS_SOURCE'),
    ('vegetarian','salt','non_veg','conflict','CONFLICT_VEG_MARK'),
    ('peanut','salt','non_veg','not_listed','NOT_LISTED_COMPLETE'),
    ('diabetes_sugar','dextrose','not_found','possible','POSSIBLE_SUGAR_ALIAS'),
    ('unknown_key','peanut','not_found','unknown','UNKNOWN_NOT_ON_LABELS'),
])
def test_ingredient_rows(make_extraction, make_profile, key, term, mark, state, code):
    actual = result(make_extraction(term, mark=mark), make_profile(key))
    assert (actual.state, actual.reason_code) == (state, code)
    if state in ('conflict','possible'):
        assert actual.evidence
        assert actual.matches


@pytest.mark.parametrize('statement_type,severity,complete,state,code', [
    ('contains','strict',True,'conflict','CONFLICT_STATEMENT'),
    ('contains','preference',True,'conflict','CONFLICT_STATEMENT'),
    ('may_contain','strict',True,'possible','POSSIBLE_MAY_CONTAIN'),
    ('facility','strict',True,'possible','POSSIBLE_FACILITY'),
    ('may_contain','preference',True,'not_listed','NOT_LISTED_TRACE_NOTE'),
    ('facility','preference',True,'not_listed','NOT_LISTED_TRACE_NOTE'),
    ('may_contain','preference',False,'unknown','UNKNOWN_TRUNCATED'),
    ('facility','preference',False,'unknown','UNKNOWN_TRUNCATED'),
    ('free_from','strict',True,'not_listed','NOT_LISTED_COMPLETE'),
])
def test_statement_rows(make_extraction, make_profile, statement_type, severity, complete, state, code):
    extraction = make_extraction('salt', complete=complete)
    extraction.allergen_statements = [AllergenStatement(id='a',type=statement_type,raw_text='PEANUT',items=['PEANUT'])]
    actual = result(extraction, make_profile('peanut', severity))
    assert (actual.state, actual.reason_code) == (state,code)
    if actual.matches:
        assert actual.matches[0].term == 'PEANUT'
        assert actual.evidence[0].status == 'unverified'


@pytest.mark.parametrize('presence,complete,issues,readability,state,kind,code', [
    ('not_found',False,[],'clear','unknown','undeterminable','UNKNOWN_SECTION_MISSING'),
    ('found',True,[],'clear','not_listed',None,'NOT_LISTED_COMPLETE'),
    ('found',False,['truncated_at_image_edge'],'clear','unknown','not_detected','UNKNOWN_TRUNCATED'),
    ('partial',False,[],'clear','unknown','not_detected','UNKNOWN_TRUNCATED'),
    ('found',False,[],'unreadable','unknown','not_detected','UNKNOWN_UNREADABLE'),
    ('found',True,[],'unreadable','unknown','not_detected','UNKNOWN_UNREADABLE'),
    ('found',True,['unreadable_span'],'clear','unknown','not_detected','UNKNOWN_UNREADABLE'),
    ('found',True,[],'partial','unknown','not_detected','UNKNOWN_UNREADABLE'),
    ('found',False,['truncated','unreadable_span'],'unreadable','unknown','not_detected','UNKNOWN_TRUNCATED'),
])
def test_absence_rows(make_extraction, make_profile, presence, complete, issues, readability, state, kind, code):
    extraction = make_extraction('salt',complete=complete,presence=presence)
    extraction.ingredients_section.issues = issues
    extraction.ingredients[0].readability = readability
    actual = result(extraction, make_profile())
    assert (actual.state,actual.unknown_kind,actual.reason_code) == (state,kind,code)


def test_conflict_survives_truncation_and_free_from(make_extraction, make_profile):
    extraction = make_extraction('Peanuts (22%)',complete=False)
    extraction.allergen_statements = [AllergenStatement(id='a',type='free_from',raw_text='Peanut free',items=['Peanut'])]
    actual = result(extraction,make_profile())
    assert actual.reason_code == 'CONFLICT_INGREDIENT'
    assert actual.message_params['term'] == 'Peanuts (22%)'


def test_green_mark_does_not_assert_absence_for_truncated_list(make_extraction, make_profile):
    assert result(make_extraction('INS 471',complete=False,mark='veg'),make_profile('vegetarian')).state == 'unknown'


def test_unreadable_nested_ingredient_prevents_absence(make_extraction, make_profile):
    extraction = make_extraction('cocoa')
    extraction.ingredients[0].sub_ingredients = [Ingredient(id='child',name='peanut',raw_text='peanut',readability='unreadable')]
    assert result(extraction,make_profile()).reason_code == 'UNKNOWN_UNREADABLE'


def test_green_egg_inconsistency_is_explicit(make_extraction, make_profile):
    actual = result(make_extraction('egg',mark='veg'),make_profile('vegetarian'))
    assert any('inconsistent' in (match.note or '').lower() for match in actual.matches)


@pytest.mark.parametrize('key,state', [('tree_nut','conflict'),('peanut','possible')])
def test_unqualified_nuts_statement(make_extraction, make_profile, key, state):
    extraction = make_extraction('salt')
    extraction.allergen_statements=[AllergenStatement(id='a',type='contains',raw_text='Contains nuts',items=['nuts'])]
    assert result(extraction,make_profile(key)).state == state


@pytest.mark.parametrize('confidence,status,expected', [(1,'verified',.8),(.5,'verified',.4),(1,'unverified',.6)])
def test_llm_caps_and_confidence(make_extraction, make_profile, confidence, status, expected):
    extraction=make_extraction('Mystery Blend')
    extraction.ingredients[0].evidence[0].status=status
    interpreted=TermInterpretation(term='mystery blend',categories=['peanut'],origin='plant',confidence=confidence,rationale='Model guess')
    actual=result(extraction,make_profile(),{'mystery blend':interpreted})
    assert actual.reason_code=='POSSIBLE_LLM_INTERPRETATION'
    assert actual.state=='possible'
    assert actual.confidence==expected


@pytest.mark.parametrize('categories,confidence', [(['invented'],1),(['peanut'],1.1),(['peanut'],-.1),(['peanut'],float('nan'))])
def test_invalid_interpretations_do_not_affect_verdict(make_extraction, make_profile, categories, confidence):
    interpreted=TermInterpretation(term='mystery',categories=categories,confidence=confidence,rationale='Invalid')
    output=engine.evaluate(make_extraction('mystery'),[make_profile()],{'mystery':interpreted})
    assert output.reports[0].results[0].state=='not_listed'
    assert output.unresolved_terms


def test_llm_cannot_reclassify_kb_ingredient(make_extraction, make_profile):
    interpreted=TermInterpretation(term='cocoa butter',categories=['milk'],confidence=1,rationale='Incorrect')
    assert result(make_extraction('cocoa butter'),make_profile('milk'),{'cocoa butter':interpreted}).state=='not_listed'


def test_ambiguous_confidence_and_unlocated_penalty(make_extraction, make_profile):
    extraction=make_extraction('INS 471')
    assert result(extraction,make_profile('vegetarian')).confidence==.7
    extraction.ingredients[0].evidence=[]
    actual=result(extraction,make_profile('vegetarian'))
    assert actual.confidence==.5
    assert actual.evidence[0].status=='unverified'


def test_table_order_precedence_evidence_and_matches(make_extraction, make_profile):
    extraction=make_extraction('natural flavours','milk')
    extraction.allergen_statements=[
        AllergenStatement(id='a',type='may_contain',raw_text='May contain milk',items=['milk'],evidence=[Evidence(image_id='img_0',text='May contain milk',status='verified')]),
        AllergenStatement(id='b',type='contains',raw_text='Contains milk',items=['milk'],evidence=[Evidence(image_id='img_0',text='Contains milk',status='verified')]),
    ]
    actual=result(extraction,make_profile('vegan'))
    assert actual.reason_code=='CONFLICT_INGREDIENT'
    assert [e.text for e in actual.evidence][:2]==['milk','Contains milk']
    assert actual.matches[0].term=='milk'
    assert any(m.term=='natural flavours' for m in actual.matches)


def test_contains_precedes_trace_even_when_listed_later(make_extraction, make_profile):
    extraction=make_extraction('salt')
    extraction.allergen_statements=[AllergenStatement(id=str(i),type=t,raw_text=t,items=['peanut']) for i,t in enumerate(['may_contain','contains'])]
    assert result(extraction,make_profile()).reason_code=='CONFLICT_STATEMENT'


def test_unknown_items_copy_regions(make_extraction):
    extraction=make_extraction('salt',complete=False,mark='unclear')
    region=Evidence(image_id='img_0',text='',status='approximate')
    extraction.ingredients_section.unreadable_regions=[region]
    output=engine.evaluate(extraction,[])
    assert any(item.region==region for item in output.unknowns)
    assert any(item.message_key=='unknown.no_allergen_statement' for item in output.unknowns)
    assert any(item.message_key=='unknown.veg_mark_unclear' for item in output.unknowns)


def test_overall_order(make_extraction, make_profile):
    profile=make_profile('peanut')
    profile.restrictions += make_profile('milk').restrictions
    assert engine.evaluate(make_extraction('peanut'),[profile]).reports[0].overall=='conflict'
    assert engine.evaluate(make_extraction('salt',complete=False),[profile]).reports[0].overall=='unknown'


@pytest.mark.parametrize('amount,expected', [(601,'conflict'),(600,'not_listed'),(599,'not_listed'),(None,'unknown')])
def test_basic_thresholds(make_extraction,make_profile,amount,expected):
    extraction=make_extraction('salt',complete=False)
    extraction.nutrition_section.presence='found'
    extraction.nutrition=NutritionTable(rows=[NutrientRow(key='sodium_mg',raw_label='Sodium',values=[NutrientValue(basis='per_100g',amount=amount,unit='mg',raw_text=str(amount))])])
    assert result(extraction,make_profile('low_sodium')).state==expected


def test_threshold_sugar_conflict_supporting_evidence(make_extraction,make_profile):
    extraction=make_extraction('Sugar')
    extraction.nutrition_section.presence='found'
    extraction.nutrition=NutritionTable(rows=[NutrientRow(key='total_sugars_g',raw_label='Total sugars',values=[NutrientValue(basis='per_100g',amount=38,unit='g',raw_text='38 g',evidence=Evidence(image_id='img_0',text='Total sugars 38 g',status='verified'))])])
    actual=result(extraction,make_profile('diabetes_sugar'))
    assert actual.reason_code=='CONFLICT_THRESHOLD'
    assert [e.text for e in actual.evidence]==['Total sugars 38 g','Sugar']
    assert [m.source for m in actual.matches]==['nutrition','kb']
