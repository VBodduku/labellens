"""Compare runs only when the complete truth set and dietary profiles are identical."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EvaluationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_digest: str
    profiles_digest: str | None
    case_ids: list[str]
    source_mode: Literal["saved", "live", "reevaluated"]
    local_engine_digest: str


class BaselineReport(BaseModel):
    evaluation: EvaluationMetadata
    metrics: dict[str, object]


def comparison(
    baseline_path: Path, current: dict[str, object], metadata: EvaluationMetadata
) -> dict[str, dict[str, object]]:
    baseline = BaselineReport.model_validate_json(
        baseline_path.read_text(encoding="utf-8")
    )
    previous = baseline.evaluation
    if (
        previous.dataset_digest != metadata.dataset_digest
        or previous.case_ids != metadata.case_ids
    ):
        raise ValueError(
            "Baseline comparison requires the same complete packet cases and unchanged truth"
        )
    if (
        not metadata.profiles_digest
        or previous.profiles_digest != metadata.profiles_digest
    ):
        raise ValueError(
            "Baseline comparison requires identical recorded evaluation profiles"
        )
    fields = (
        "ingredient_precision",
        "ingredient_recall",
        "nutrient_accuracy",
        "statement_accuracy",
        "veg_mark_accuracy",
        "verdict_accuracy",
        "dangerous_misses",
        "dangerous_miss_rate",
        "evidence_verified_rate",
        "unknown_rate",
        "average_latency_ms",
    )
    result: dict[str, dict[str, object]] = {}
    for field in fields:
        before, after = baseline.metrics.get(field), current.get(field)
        change = (
            float(after) - float(before)
            if isinstance(before, (float, int)) and isinstance(after, (float, int))
            else None
        )
        result[field] = dict(before=before, after=after, change=change)
    return result


def markdown_table(rows: dict[str, dict[str, object]]) -> list[str]:
    def display(value: object) -> str:
        return (
            "unmeasured"
            if value is None
            else f"{value:.4f}"
            if isinstance(value, float)
            else str(value)
        )

    return [
        "",
        "## Before / after (same truth and profiles)",
        "",
        "| Metric | Before | After | Change |",
        "| --- | --- | --- | --- |",
    ] + [
        f"| {field} | {display(row['before'])} | {display(row['after'])} | {display(row['change'])} |"
        for field, row in rows.items()
    ]
