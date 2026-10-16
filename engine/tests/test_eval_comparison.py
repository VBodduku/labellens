import json
from pathlib import Path

import pytest
from shared.contract import IngredientAnnotation, ScanResult, Match
from engine.eval.build_synthetic import build
from engine.eval.errors import ErrorReview
from engine.eval.replay import load_profiles, replay
from engine.eval.run_eval import run, score_packet, Truth


def profiles():
    return load_profiles(Path("engine/eval/eval_profiles.json"))


def test_before_after_uses_same_truth_and_profiles_and_preserves_raw(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    baseline = tmp_path / "before"
    run(dataset, responses, baseline, profiles=profiles())
    original = {path.name: path.read_bytes() for path in responses.glob("*.json")}
    run(
        dataset,
        responses,
        tmp_path / "after",
        profiles=profiles(),
        reevaluate=True,
        baseline=baseline / "report.json",
    )
    report = json.loads((tmp_path / "after/report.json").read_text())
    assert report["evaluation"]["source_mode"] == "reevaluated"
    assert "verdict_accuracy" in report["comparison"]
    assert "Before / after" in (tmp_path / "after/report.md").read_text()
    assert original == {
        path.name: path.read_bytes() for path in responses.glob("*.json")
    }
    assert len(list((responses / "reevaluated").glob("*.json"))) == 2
    assert report["metrics"]["average_latency_ms"] is None


@pytest.mark.parametrize("change", ["truth", "profiles", "unrecorded_profiles"])
def test_unfair_baseline_comparison_fails_without_reports(tmp_path, change):
    dataset, responses = build(tmp_path / "synthetic")
    before = tmp_path / "before"
    run(
        dataset,
        responses,
        before,
        profiles=None if change == "unrecorded_profiles" else profiles(),
    )
    current = profiles()
    if change == "truth":
        path = dataset / "synthetic_clean/truth.json"
        truth = json.loads(path.read_text())
        truth["product"] = "changed reference"
        path.write_text(json.dumps(truth))
    elif change == "profiles":
        current[0].name = "Changed profile"
    with pytest.raises(ValueError, match="Baseline comparison"):
        run(
            dataset,
            responses,
            tmp_path / "after",
            profiles=current,
            baseline=before / "report.json",
        )
    assert not (tmp_path / "after").exists()


def test_overwriting_baseline_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="overwritten"):
        dataset, responses = build(tmp_path / "synthetic")
        run(
            dataset,
            responses,
            tmp_path / "reports",
            baseline=tmp_path / "reports/report.json",
        )


def test_missing_unknown_profile_does_not_count_as_correct():
    scan = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    truth = Truth(
        product="Synthetic",
        ingredients=[],
        ingredients_complete_in_photos=False,
        allergen_statements={},
        veg_mark="veg",
        nutrition_per_100={},
        expected=[dict(eval_profile="missing", state="unknown")],
    )
    scores = score_packet(truth, scan)
    assert scores["verdict_correct"] == 0
    assert scores["missing_profiles"] == ["missing"]


def test_fixture_responses_cannot_be_relabelled_real(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    for path in dataset.glob("*/truth.json"):
        truth = json.loads(path.read_text())
        truth["source"] = "real"
        path.write_text(json.dumps(truth))
    with pytest.raises(ValueError, match="Fixture extraction"):
        run(dataset, responses, tmp_path / "reports")


def test_failed_capture_cannot_use_stale_files(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    (responses / "capture_manifest.json").write_text(
        json.dumps(dict(failed=["synthetic_clean"]))
    )
    with pytest.raises(ValueError, match="stale and fresh"):
        run(dataset, responses, tmp_path / "reports")


def test_error_audit_does_not_invent_cause_or_zero_engine_misses(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    path = responses / "synthetic_clean.json"
    scan = ScanResult.model_validate_json(path.read_text())
    target = next(report for report in scan.reports if report.overall == "conflict")
    target.overall = "not_listed"
    path.write_text(scan.model_dump_json())
    metrics = run(dataset, responses, tmp_path / "unreviewed")
    assert metrics["engine_dangerous_misses"] is None
    assert metrics["unreviewed_dangerous_misses"] == 1
    review = tmp_path / "review.json"
    review.write_text(
        json.dumps(
            {
                f"synthetic_clean:verdict:{target.profile_id}": dict(
                    category="rule_bug",
                    explanation="Synthetic test deliberately corrupts the overall verdict.",
                    regression_test="engine/tests/test_eval_comparison.py::test_error_audit_does_not_invent_cause_or_zero_engine_misses",
                )
            }
        )
    )
    reviewed = run(dataset, responses, tmp_path / "reviewed", reviews_path=review)
    assert reviewed["engine_dangerous_misses"] == 1


@pytest.mark.parametrize("category", ["kb_gap", "matcher_bug", "rule_bug"])
def test_engine_classification_requires_test(category):
    with pytest.raises(ValueError, match="regression test"):
        ErrorReview(category=category, explanation="Reviewed error")


def test_replay_refuses_to_drop_original_llm_signal(tmp_path):
    scan = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    scan.extraction.ingredients[0].name = "xyzzy protein"
    scan.annotations = [
        IngredientAnnotation(
            ingredient_id=scan.extraction.ingredients[0].id,
            canonical_ids=[],
            categories=["milk"],
            origin="animal",
            source="llm_interpretation",
        )
    ]
    with pytest.raises(ValueError, match="Original LLM inputs are missing"):
        replay(scan, profiles(), tmp_path / "missing.interpretations.json")


def test_replay_accepts_original_interpretation_sidecar(tmp_path):
    scan = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    scan.extraction.ingredients[0].name = "xyzzy protein"
    sidecar = tmp_path / "case.interpretations.json"
    sidecar.write_text(
        json.dumps(
            {
                "xyzzy protein": dict(
                    term="xyzzy protein",
                    categories=["milk"],
                    confidence=0.9,
                    origin="animal",
                    rationale="Synthetic test interpretation",
                )
            }
        )
    )
    result = replay(scan, profiles(), sidecar)
    assert result.extraction == scan.extraction
    assert any(
        annotation.source == "llm_interpretation" for annotation in result.annotations
    )


def test_partial_kb_annotation_does_not_hide_original_llm_signal(tmp_path):
    scan = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    ingredient = scan.extraction.ingredients[0]
    ingredient.name = "wheat flour xyzzy"
    scan.annotations = [
        IngredientAnnotation(
            ingredient_id=ingredient.id,
            canonical_ids=["wheat_flour"],
            categories=["wheat", "gluten"],
            origin="plant",
            source="kb",
        )
    ]
    scan.reports[0].results[0].matches.append(
        Match(
            ingredient_id=ingredient.id,
            term=ingredient.name,
            category="milk",
            source="llm_interpretation",
        )
    )
    with pytest.raises(ValueError, match="Original LLM inputs are missing"):
        replay(scan, profiles(), tmp_path / "missing.interpretations.json")


def test_changed_photo_prevents_baseline_comparison(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    photo = dataset / "synthetic_clean/img_0.jpg"
    photo.write_bytes(b"original transport test photo")
    run(dataset, responses, tmp_path / "before", profiles=profiles())
    photo.write_bytes(b"different transport test photo")
    with pytest.raises(ValueError, match="Baseline comparison"):
        run(
            dataset,
            responses,
            tmp_path / "after",
            profiles=profiles(),
            baseline=tmp_path / "before/report.json",
        )


def test_capture_profiles_cannot_be_relabelled_after_scan(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    captured = profiles()
    (responses / "capture_manifest.json").write_text(
        json.dumps(
            dict(failed=[], profiles=[p.model_dump(mode="json") for p in captured])
        )
    )
    changed = profiles()
    changed[0].name = "Different profile"
    with pytest.raises(ValueError, match="differ from those submitted"):
        run(dataset, responses, tmp_path / "reports", profiles=changed)


def test_checked_in_synthetic_error_reviews_cover_controlled_corruptions(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    metrics = run(
        dataset,
        responses,
        tmp_path / "reports",
        profiles=profiles(),
        reviews_path=Path("engine/eval/synthetic/classifications.json"),
    )
    assert metrics["error_count"] == 3
    assert metrics["unreviewed_error_count"] == 0
    report = json.loads((tmp_path / "reports/report.json").read_text())
    assert all(error["category"] == "extraction" for error in report["errors"])
