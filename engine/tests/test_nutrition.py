import pytest
import engine
from shared.contract import NutritionTable,NutrientRow,NutrientValue
from engine.nutrition import readable_values,value_at_basis
from engine.messages import render


def table(key='total_sugars_g',amount=10,unit='g',basis='per_serving',label='Total sugars',**kwargs):
    return NutritionTable(rows=[NutrientRow(key=key,raw_label=label,values=[NutrientValue(basis=basis,amount=amount,unit=unit,raw_text=str(amount))])],**kwargs)


@pytest.mark.parametrize('key,amount,unit,label,expected',[
    ('energy_kcal',418.4,'kJ','Energy',100),
    ('sodium_mg',.5,'g','Sodium',500),
    ('sodium_mg',1,'g','Salt',400),
    ('total_sugars_g',1000,'mg','Sugars',1),
    ('total_sugars_g',1000000,'mcg','Sugars',1),
])
def test_unit_conversions(key,amount,unit,label,expected):
    actual=readable_values(table(key,amount,unit,label=label))
    assert actual[(key,'per_serving')][0]==pytest.approx(expected)


def test_per_100_and_pack(make_extraction):
    extraction=make_extraction('sugar')
    extraction.nutrition=table(serving_size=40,serving_unit='g',pack_size=120,pack_unit='g',servings_per_pack=3)
    analysis=engine.analyze_nutrition(extraction)
    assert analysis.per_100['total_sugars_g']==25
    assert analysis.per_pack['total_sugars_g']==30
    assert analysis.notes==['nutrition.serving_small']
    assert analysis.consistency.status=='insufficient_data'


def test_volume_does_not_convert_to_mass():
    t=table(basis='per_100ml',serving_size=20,serving_unit='ml')
    assert value_at_basis(t,'total_sugars_g','per_100g') is None
    assert value_at_basis(t,'total_sugars_g','per_serving')[0]==2


@pytest.mark.parametrize('unit,amount,readability',[('ounces',1,'clear'),('g',float('nan'),'clear'),('g',-1,'clear'),('g',None,'clear'),('g',1,'unreadable'),('g',1,'partial')])
def test_invalid_and_unreadable_values_are_not_compared(unit,amount,readability):
    t=table(unit=unit,amount=amount)
    t.rows[0].values[0].readability=readability
    assert readable_values(t)=={}


def test_conflicting_duplicate_nutrients_not_used():
    t=table(amount=10)
    t.rows[0].values += [NutrientValue(basis='per_serving',amount=50,unit='g',raw_text='50'),NutrientValue(basis='per_serving',amount=10,unit='g',raw_text='10')]
    assert not readable_values(t)


def test_message_rendering_keeps_wire_params():
    params={'term':'Natural Flavours','category':'onion|garlic'}
    assert render('verdict.possible.ambiguous_source',params)=='Natural Flavours can come from onion or garlic sources; the label does not say which.'
    assert params['category']=='onion|garlic'
    params={'nutrient':'total_sugars_g','basis':'per_100g','value':38.,'limit':22.5,'unit':'g'}
    assert 'per 100 g' in render('verdict.conflict.threshold',params)
