import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from shared.contract import ScanResult
from engine.eval.metrics import matched_ingredients, ratio, score_verdicts
from engine.eval.run_eval import Truth, run, score_packet


def test_ingredient_matching_is_one_to_one():
    assert matched_ingredients(["sugar", "milk"], ["sugar", "sugar"]) == 1
    assert ratio(0, 0) is None


def test_confusion_and_dangerous_misses():
    result = score_verdicts(
        [("conflict", "not_listed"), ("conflict", "unknown"), ("possible", "possible")]
    )
    assert result.dangerous_misses == 1
    assert result.expected_conflicts == 2
    assert result.correct == 1
    assert result.confusion["conflict"]["unknown"] == 1


def test_empty_real_dataset_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="No real packet"):
        run(tmp_path, tmp_path, tmp_path / "reports")
    assert not (tmp_path / "reports").exists()


def fixture():
    path = Path(__file__).resolve().parents[2] / "shared/fixtures/scan_result.json"
    return ScanResult.model_validate_json(path.read_text(encoding="utf-8"))


def test_saved_response_harness_writes_three_files(tmp_path):
    scan = fixture()
    truth = Truth(
        source="synthetic",
        product="Synthetic fixture, not a real-packet accuracy measurement",
        ingredients=[i.name for i in scan.extraction.ingredients],
        ingredients_complete_in_photos=True,
        allergen_statements={
            s.type: s.items for s in scan.extraction.allergen_statements
        },
        veg_mark="veg",
        nutrition_per_100={"total_sugars_g": 38},
        expected=[{"eval_profile": "p_aarav", "state": "conflict"}],
    )
    packet = tmp_path / "dataset" / "synthetic"
    packet.mkdir(parents=True)
    responses = tmp_path / "responses"
    responses.mkdir()
    (packet / "truth.json").write_text(truth.model_dump_json(), encoding="utf-8")
    (responses / "synthetic.json").write_text(scan.model_dump_json(), encoding="utf-8")
    metrics = run(packet.parent, responses, tmp_path / "reports")
    assert metrics["dangerous_miss_rate"] == 0
    assert metrics["verdict_accuracy"] == 1
    for name in ["metrics.json", "report.json", "report.md"]:
        assert (tmp_path / "reports" / name).is_file()
    headline = json.loads((tmp_path / "reports/metrics.json").read_text())
    assert headline["status"] == "pending"
    assert headline["metrics"]["packets"] == 0


def test_missing_profile_is_unknown_not_not_listed():
    truth = Truth(
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={},
        expected=[{"eval_profile": "absent", "state": "conflict"}],
    )
    score = score_packet(truth, fixture())
    assert score["verdict_pairs"] == [("conflict", "unknown")]
    assert score["missing_profiles"] == ["absent"]


@pytest.mark.parametrize(
    "expected,predicted,rounding,correct",
    [
        (10, 10.2, 0, 1),
        (10, 10.21, 0, 0),
        (10, 10.4, 0.5, 1),
        (0, 0.01, 0, 0),
        (0, 0.01, 0.01, 1),
    ],
)
def test_nutrient_tolerance_is_relative_or_printed_rounding(
    expected, predicted, rounding, correct
):
    scan = fixture()
    scan.nutrition_analysis.per_100 = {"sodium_mg": predicted}
    truth = Truth(
        source="synthetic",
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={"sodium_mg": expected},
        nutrition_rounding={"sodium_mg": rounding},
        expected=[],
    )
    assert score_packet(truth, scan)["nutrient_correct"] == correct


@pytest.mark.parametrize(
    "change",
    [
        {"nutrition_per_100": {"sodium_mg": float("nan")}},
        {"nutrition_per_100": {"misspelled": 1}},
        {"nutrition_rounding": {"sodium_mg": -0.5}},
        {
            "expected": [
                {"eval_profile": "p", "state": "conflict"},
                {"eval_profile": "p", "state": "unknown"},
            ]
        },
    ],
)
def test_bad_truth_rejected(change):
    data = dict(
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={"sodium_mg": 1},
        expected=[],
    )
    data.update(change)
    with pytest.raises(ValueError):
        Truth.model_validate(data)


def test_two_synthetic_packets_end_to_end_and_reproducible(tmp_path):
    from engine.eval.build_synthetic import build

    dataset, responses = build(tmp_path / "synthetic")
    reports = tmp_path / "reports"
    generated = datetime(2026, 10, 16, tzinfo=timezone.utc)
    metrics = run(dataset, responses, reports, generated_at=generated)
    assert metrics["dataset_kind"] == "synthetic"
    assert metrics["real_packets"] == 0
    assert metrics["packets"] == 2
    assert metrics["dangerous_misses"] == 0
    assert metrics["expected_conflicts"] == 9
    assert metrics["confusion_matrix"]["conflict"]["possible"] == 1
    assert metrics["average_latency_ms"] is None
    assert metrics["missing_profile_count"] == 0
    assert "NOT real-packet accuracy" in (reports / "report.md").read_text(
        encoding="utf-8"
    )
    before = {path.name: path.read_bytes() for path in reports.iterdir()}
    build(tmp_path / "synthetic")
    run(dataset, responses, reports, generated_at=generated)
    assert before == {path.name: path.read_bytes() for path in reports.iterdir()}


def test_real_and_synthetic_cases_cannot_mix(tmp_path):
    from engine.eval.build_synthetic import build

    dataset, responses = build(tmp_path / "synthetic")
    target = dataset / "synthetic_clean/truth.json"
    truth = json.loads(target.read_text(encoding="utf-8"))
    truth["source"] = "real"
    target.write_text(json.dumps(truth), encoding="utf-8")
    with pytest.raises(ValueError, match="mix real and synthetic"):
        run(dataset, responses, tmp_path / "reports")
    assert not (tmp_path / "reports").exists()


def test_synthetic_latency_is_unmeasured_but_real_saved_latency_is_used():
    scan = fixture()
    truth = Truth(
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={},
        expected=[],
    )
    assert score_packet(truth, scan)["latency_ms"] == 4120
    truth.source = "synthetic"
    assert score_packet(truth, scan)["latency_ms"] is None


def test_missing_saved_response_does_not_write_partial_reports(tmp_path):
    from engine.eval.build_synthetic import build

    dataset, responses = build(tmp_path / "synthetic")
    (responses / "synthetic_imperfect.json").unlink()
    with pytest.raises(FileNotFoundError):
        run(dataset, responses, tmp_path / "reports")
    assert not (tmp_path / "reports").exists()


def test_nutrients_at_different_mass_volume_bases_do_not_score_as_equal():
    scan = fixture()
    truth = Truth(
        source="synthetic",
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={"total_sugars_g": 38},
        nutrition_per_100_unit="ml",
        expected=[],
    )
    assert score_packet(truth, scan)["nutrient_correct"] == 0
