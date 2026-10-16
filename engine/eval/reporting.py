"""Readable audit reports and the existing About-page status/metrics envelope."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Annotated, Literal, cast

from pydantic import BaseModel, ConfigDict, Field
from engine.eval.comparison import EvaluationMetadata, markdown_table
from engine.eval.errors import EvaluationError
from engine.eval.metrics import STATES

Rate = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class HeadlineValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    packets: int = Field(ge=0)
    ingredient_recall: Rate | None = None
    ingredient_precision: Rate | None = None
    nutrient_accuracy: Rate | None = None
    verdict_accuracy: Rate | None = None
    dangerous_miss_rate: Rate | None = None
    evidence_verified_rate: Rate | None = None
    unknown_rate: Rate | None = None
    avg_latency_s: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class AboutMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "ready"]
    metrics: HeadlineValues
    generated_at: str


def timestamp(now: datetime) -> str:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Report generation time must have an explicit timezone")
    return (
        now.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def about_metrics(metrics: Mapping[str, object], generated_at: str) -> AboutMetrics:
    real = metrics.get("dataset_kind") == "real" and bool(metrics.get("real_packets"))
    fields = {
        key: metrics.get(key)
        for key in HeadlineValues.model_fields
        if key not in {"packets", "avg_latency_s"}
    }
    latency = metrics.get("average_latency_ms")
    fields.update(
        packets=metrics.get("real_packets", 0),
        avg_latency_s=float(latency) / 1000
        if isinstance(latency, (float, int))
        else None,
    )
    if not real:
        fields = {key: None for key in fields}
        fields["packets"] = 0
    return AboutMetrics(
        status="ready" if real else "pending",
        metrics=HeadlineValues.model_validate(fields),
        generated_at=generated_at,
    )


def _percent(value: object) -> str:
    return f"{value:.2%}" if isinstance(value, (float, int)) else "unmeasured"


def _cell(value: object) -> str:
    return (
        ("unmeasured" if value is None else str(value))
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def render_report(
    metrics: Mapping[str, object],
    metadata: EvaluationMetadata,
    errors: Sequence[EvaluationError],
    changes: dict[str, dict[str, object]] | None,
    generated_at: str,
) -> str:
    synthetic = metrics["dataset_kind"] == "synthetic"
    title = (
        "Synthetic pipeline check — NOT real-packet accuracy"
        if synthetic
        else "Real-packet evaluation"
    )
    lines = [
        f"# {title}",
        "",
        f"Generated: {generated_at}. Cases: {metrics['packets']}; real cases: {metrics['real_packets']}.",
        "",
    ]
    if synthetic:
        lines += [
            "**No real-packet headline metrics are available.** These fixture-derived software checks cannot substantiate a pitch accuracy claim. About-page metrics remain pending, with zero real packets and null rates.",
            "",
        ]
    lines += ["## Extraction accuracy", "", "| Measure | Accuracy |", "| --- | ---: |"]
    for label, key in (
        ("Ingredient precision", "ingredient_precision"),
        ("Ingredient recall", "ingredient_recall"),
        ("Nutrient values", "nutrient_accuracy"),
        ("Allergen statements (exact sets)", "statement_accuracy"),
        ("Veg mark", "veg_mark_accuracy"),
    ):
        lines.append(f"| {label} | {_percent(metrics[key])} |")
    lines += [
        "",
        "## Verdicts, evidence and unknowns",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Verdict accuracy (profile overall) | {_percent(metrics['verdict_accuracy'])} |",
        f"| Dangerous-miss rate | {_percent(metrics['dangerous_miss_rate'])} ({metrics['dangerous_misses']} / {metrics['expected_conflicts']} expected conflicts) |",
        f"| Engine-caused dangerous misses | {_cell(metrics['engine_dangerous_misses'])} |",
        f"| Extraction-caused dangerous misses | {metrics['extraction_dangerous_misses']} |",
        f"| Unreviewed dangerous misses | {metrics['unreviewed_dangerous_misses']} |",
        f"| Evidence verified rate | {_percent(metrics['evidence_verified_rate'])} |",
        f"| Unknown rate (restriction results) | {_percent(metrics['unknown_rate'])} |",
        f"| Missing expected profiles | {metrics['missing_profile_count']} |",
        "",
        "A dangerous miss is expected conflict → predicted not_listed. Conflict → possible/unknown also fails verdict accuracy; inspect the matrix and error audit.",
        "",
        "## Verdict confusion matrix",
        "",
        "Rows are expected states; columns are predicted states.",
        "",
        "| Expected / predicted | " + " | ".join(STATES) + " |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    matrix = cast(dict[str, dict[str, int]], metrics["confusion_matrix"])
    for state in STATES:
        lines.append(
            "| "
            + state
            + " | "
            + " | ".join(str(matrix[state][predicted]) for predicted in STATES)
            + " |"
        )
    latency = metrics["average_latency_ms"]
    seconds = (
        f"{latency / 1000:.3f} s" if isinstance(latency, (float, int)) else "unmeasured"
    )
    lines += [
        "",
        "## Latency",
        "",
        "| Measure | Value |",
        "| --- | ---: |",
        f"| Mean backend request duration | {seconds} |",
        f"| Timed requests | {metrics['latency_samples']} |",
        f"| Cache hits in timed requests | {metrics['latency_cache_hits']} |",
        "",
        "Measured by the capture client, including upload and backend response work; browser capture/render time is excluded. Saved extraction-only durations and offline replays are not end-to-end request measurements. Cache hits remain included and are counted above.",
        "",
    ]
    if changes:
        lines += markdown_table(changes)
        lines += [
            "",
            "Comparison rates above are fractions (0–1); latency is milliseconds. Both runs use the same truth, photos and profiles.",
        ]
    lines += [
        "",
        "## Error analysis",
        "",
        "| Packet / error ID | Check | Expected | Predicted | Cause | Review |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for error in errors:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    error.error_id,
                    error.check,
                    error.expected,
                    error.predicted,
                    error.category,
                    error.explanation,
                )
            )
            + " |"
        )
    if not errors:
        lines.append("| — | No scored discrepancies | — | — | — | — |")
    lines += ["", "## Scope and limitations", ""]
    limitations = cast(list[str], metrics["limitations"])
    lines += [f"- {limitation}" for limitation in limitations]
    lines += [
        "",
        f"Source mode: {metadata.source_mode}. Local engine fingerprint: {metadata.local_engine_digest}.",
        f"Truth/photo fingerprint: {metadata.dataset_digest}. Profiles fingerprint: {metadata.profiles_digest or 'unrecorded'}.",
    ]
    return "\n".join(lines) + "\n"
