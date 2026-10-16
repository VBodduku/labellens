"""Publication format checks use simulated data, not real-packet measurements."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from engine.eval.build_synthetic import build
from engine.eval.reporting import AboutMetrics, about_metrics, timestamp
from engine.eval.run_eval import run

NOW = datetime(2026, 10, 16, 12, 30, tzinfo=timezone.utc)
KEYS = {
    "packets",
    "ingredient_recall",
    "ingredient_precision",
    "nutrient_accuracy",
    "verdict_accuracy",
    "dangerous_miss_rate",
    "evidence_verified_rate",
    "unknown_rate",
    "avg_latency_s",
}


def metrics(kind="real"):
    return dict(
        dataset_kind=kind,
        real_packets=2 if kind == "real" else 0,
        ingredient_recall=0.9,
        ingredient_precision=0.8,
        nutrient_accuracy=0.7,
        verdict_accuracy=0.6,
        dangerous_miss_rate=0.1,
        evidence_verified_rate=0.5,
        unknown_rate=0.2,
        average_latency_ms=1500.0,
    )


def test_about_envelope_matches_existing_frontend_loader():
    result = about_metrics(metrics(), timestamp(NOW)).model_dump(mode="json")
    assert set(result) == {"status", "metrics", "generated_at"}
    assert result["status"] == "ready"
    assert set(result["metrics"]) == KEYS
    assert result["metrics"]["avg_latency_s"] == 1.5
    assert (
        result["metrics"]["ingredient_recall"] == 0.9
    )  # Fractions, not percent points.
    assert result["generated_at"] == "2026-10-16T12:30:00Z"
    AboutMetrics.model_validate_json(json.dumps(result, allow_nan=False))


def test_synthetic_scores_cannot_leak_into_about_headlines():
    result = about_metrics(metrics("synthetic"), timestamp(NOW))
    assert result.status == "pending" and result.metrics.packets == 0
    assert all(
        value is None
        for key, value in result.metrics.model_dump().items()
        if key != "packets"
    )


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_headline_rate_rejected(value):
    data = metrics()
    data["ingredient_recall"] = value
    with pytest.raises(ValueError):
        about_metrics(data, timestamp(NOW))


def test_timestamp_converts_to_utc_and_rejects_naive_time():
    assert (
        timestamp(NOW.astimezone(timezone(timedelta(hours=5, minutes=30))))
        == "2026-10-16T12:30:00Z"
    )
    with pytest.raises(ValueError, match="timezone"):
        timestamp(NOW.replace(tzinfo=None))


def test_readable_report_has_all_required_tables_and_pending_publication(tmp_path):
    dataset, responses = build(tmp_path / "synthetic")
    run(dataset, responses, tmp_path / "reports", generated_at=NOW)
    report = (tmp_path / "reports/report.md").read_text()
    for text in [
        "## Extraction accuracy",
        "## Verdict confusion matrix",
        "## Latency",
        "Dangerous-miss rate",
        "Evidence verified rate",
        "Unknown rate",
        "NOT real-packet accuracy",
    ]:
        assert text in report
    assert "```json" not in report  # Matrix is a readable table.
    headline = json.loads((tmp_path / "reports/metrics.json").read_text())
    assert headline["status"] == "pending"
    assert len(headline["metrics"]) == 9
    assert (
        json.loads((tmp_path / "reports/report.json").read_text())["metrics"]["packets"]
        == 2
    )


@pytest.mark.parametrize(
    "recorded,reevaluate,expected",
    [(True, False, 1.5), (False, False, None), (True, True, None)],
)
def test_request_latency_uses_transport_measurement_not_extraction_duration(
    tmp_path, recorded, reevaluate, expected
):
    from engine.eval.replay import load_profiles
    from pathlib import Path

    dataset, responses = build(tmp_path / "simulated_real_transport")
    cases = []
    for path in dataset.glob("*/truth.json"):
        truth = json.loads(path.read_text())
        truth["source"] = "real"
        path.write_text(json.dumps(truth))
        response_path = responses / f"{path.parent.name}.json"
        scan = json.loads(response_path.read_text())
        # Simulates a live transport's contract; never written into the actual dataset.
        scan["extraction"]["meta"]["provider"] = "gemini"
        scan["extraction"]["meta"]["duration_ms"] = 7
        response_path.write_text(json.dumps(scan))
        cases.append(
            dict(
                packet_id=path.parent.name,
                status="captured",
                request_ms=1500.0,
                cache_hit=True,
            )
        )
    if recorded:
        (responses / "capture_manifest.json").write_text(
            json.dumps(dict(failed=[], cases=cases))
        )
    result = run(
        dataset,
        responses,
        tmp_path / "reports",
        reevaluate=reevaluate,
        profiles=load_profiles(Path("engine/eval/eval_profiles.json")),
        generated_at=NOW,
    )
    public = AboutMetrics.model_validate_json(
        (tmp_path / "reports/metrics.json").read_text()
    )
    assert public.status == "ready" and public.metrics.packets == 2
    assert public.metrics.avg_latency_s == expected
    assert result["latency_cache_hits"] == (2 if expected is not None else 0)
