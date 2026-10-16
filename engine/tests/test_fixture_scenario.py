import json
from pathlib import Path
import engine
from shared.contract import Profile, ScanResult
from shared.engine_interface import EngineOutput

ROOT=Path(__file__).resolve().parents[2]


def test_fixture_states_kinds_and_reasons():
    expected=ScanResult.model_validate_json((ROOT/'shared/fixtures/scan_result.json').read_text(encoding='utf-8'))
    profiles=[Profile.model_validate(p) for p in json.loads((ROOT/'shared/fixtures/profiles.json').read_text(encoding='utf-8'))]
    output=engine.evaluate(expected.extraction,profiles)
    EngineOutput.model_validate_json(output.model_dump_json())
    for actual,truth in zip(output.reports,expected.reports,strict=True):
        assert actual.profile_id==truth.profile_id
        assert actual.overall==truth.overall
        assert actual.summary is None
        for result,wanted in zip(actual.results,truth.results,strict=True):
            assert (result.restriction_id,result.state,result.unknown_kind,result.reason_code)==(wanted.restriction_id,wanted.state,wanted.unknown_kind,wanted.reason_code)
    assert not output.unresolved_terms


def test_deterministic_without_mutating_inputs(make_extraction, make_profile):
    extraction=make_extraction('INS 471','milk')
    profile=make_profile('vegan')
    before=extraction.model_dump_json(),profile.model_dump_json()
    a=engine.evaluate(extraction,[profile]).model_dump_json()
    b=engine.evaluate(extraction,[profile]).model_dump_json()
    assert a==b
    assert before==(extraction.model_dump_json(),profile.model_dump_json())
