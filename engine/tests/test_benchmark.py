import json
from pathlib import Path

import pytest
from shared.contract import Ingredient, ScanResult
from engine.eval.benchmark import ingredient_size, largest_real, measure
from engine.eval.build_synthetic import build
from engine.eval.replay import load_profiles


def test_fixture_timing_cannot_satisfy_real_packet_target():
    extraction = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    ).extraction
    result = measure(
        extraction,
        load_profiles(Path("engine/eval/eval_profiles.json")),
        kind="fixture",
        samples=2,
        warmups=0,
    )
    assert result["measurement_kind"] == "fixture" and result["real_target_met"] is None
    assert result["ingredient_nodes"] == len(extraction.ingredients)
    assert result["median_ms"] >= 0 and result["p95_ms"] >= result["median_ms"]


def test_largest_real_does_not_fall_back_to_synthetic(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    with pytest.raises(ValueError, match="No saved real extractions"):
        largest_real(dataset, responses)


def test_real_case_with_fixture_provider_rejected(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    truth_file = dataset / "synthetic_clean/truth.json"
    truth = json.loads(truth_file.read_text())
    truth["source"] = "real"
    truth_file.write_text(json.dumps(truth))
    with pytest.raises(ValueError, match="fixture extraction"):
        largest_real(dataset, responses)


def test_ingredient_workload_counts_nested_names():
    items = [
        Ingredient(
            id="parent",
            name="",
            raw_text="",
            sub_ingredients=[Ingredient(id="c", name="peanuts", raw_text="peanuts")],
        )
    ]
    assert ingredient_size(items) == (2, 7)


@pytest.mark.parametrize("samples,warmups", [(0, 0), (1, -1)])
def test_invalid_benchmark_sample_counts_rejected(samples, warmups):
    scan = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    with pytest.raises(ValueError, match="Samples"):
        measure(scan.extraction, [], kind="fixture", samples=samples, warmups=warmups)
