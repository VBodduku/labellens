import json
from pathlib import Path
import pytest
from shared.contract import ScanResult
from engine.eval.metrics import matched_ingredients,ratio,score_verdicts
from engine.eval.run_eval import Truth,run,score_packet


def test_ingredient_matching_is_one_to_one():
    assert matched_ingredients(['sugar','milk'],['sugar','sugar'])==1
    assert ratio(0,0) is None


def test_confusion_and_dangerous_misses():
    result=score_verdicts([('conflict','not_listed'),('conflict','unknown'),('possible','possible')])
    assert result.dangerous_misses==1
    assert result.expected_conflicts==2
    assert result.correct==1
    assert result.confusion['conflict']['unknown']==1


def test_empty_real_dataset_is_rejected(tmp_path):
    with pytest.raises(ValueError,match='No real packet'):
        run(tmp_path,tmp_path,tmp_path/'reports')
    assert not (tmp_path/'reports').exists()


def fixture():
    path=Path(__file__).resolve().parents[2]/'shared/fixtures/scan_result.json'
    return ScanResult.model_validate_json(path.read_text(encoding='utf-8'))


def test_saved_response_harness_writes_three_files(tmp_path):
    scan=fixture()
    truth=Truth(product='Synthetic fixture, not a real-packet accuracy measurement',
                ingredients=[i.name for i in scan.extraction.ingredients],ingredients_complete_in_photos=True,
                allergen_statements={s.type:s.items for s in scan.extraction.allergen_statements},
                veg_mark='veg',nutrition_per_100={'total_sugars_g':38},
                expected=[{'eval_profile':'p_aarav','state':'conflict'}])
    packet=tmp_path/'dataset'/'synthetic'
    packet.mkdir(parents=True)
    responses=tmp_path/'responses'
    responses.mkdir()
    (packet/'truth.json').write_text(truth.model_dump_json(),encoding='utf-8')
    (responses/'synthetic.json').write_text(scan.model_dump_json(),encoding='utf-8')
    metrics=run(packet.parent,responses,tmp_path/'reports')
    assert metrics['dangerous_miss_rate']==0
    assert metrics['verdict_accuracy']==1
    for name in ['metrics.json','report.json','report.md']:
        assert (tmp_path/'reports'/name).is_file()
    assert json.loads((tmp_path/'reports/metrics.json').read_text())['packets']==1


def test_missing_profile_is_unknown_not_not_listed():
    truth=Truth(product='Synthetic',ingredients=[],ingredients_complete_in_photos=False,
                allergen_statements={},veg_mark='veg',nutrition_per_100={},
                expected=[{'eval_profile':'absent','state':'conflict'}])
    score=score_packet(truth,fixture())
    assert score['verdict_pairs']==[('conflict','unknown')]
    assert score['missing_profiles']==['absent']
