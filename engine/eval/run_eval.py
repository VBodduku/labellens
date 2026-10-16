"""Score saved ScanResult responses against independent truth, with explicit dataset provenance."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.contract import (
    Evidence,
    Ingredient,
    NUTRIENT_KEYS,
    ScanResult,
    VerdictState,
)
from engine.eval.metrics import matched_ingredients, ratio, score_verdicts
from engine.normalize import normalize

HERE = Path(__file__).resolve().parent
CountKey = Literal[
    "ingredient_matches",
    "ingredients_expected",
    "ingredients_predicted",
    "nutrient_correct",
    "nutrients_expected",
    "evidence_verified",
    "evidence_total",
    "unknown_results",
    "total_results",
]


class PacketScores(TypedDict):
    ingredient_matches: int
    ingredients_expected: int
    ingredients_predicted: int
    nutrient_correct: int
    nutrients_expected: int
    statements_exact: bool
    veg_mark_correct: bool
    verdict_pairs: list[tuple[VerdictState, VerdictState]]
    missing_profiles: list[str]
    evidence_verified: int
    evidence_total: int
    unknown_results: int
    total_results: int
    latency_ms: int | None


class PacketRecord(PacketScores):
    packet_id: str


class ExpectedVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eval_profile: str
    state: VerdictState


class Truth(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: Literal["real", "synthetic"] = "real"
    product: str
    ingredients: list[str]
    ingredients_complete_in_photos: bool
    allergen_statements: dict[str, list[str]]
    veg_mark: Literal["veg", "non_veg", "not_found", "unclear"]
    nutrition_per_100: dict[str, float]
    nutrition_per_100_unit: Literal["g", "ml"] = "g"
    # Absolute tolerance in canonical units: half the last printed digit's place value.
    nutrition_rounding: dict[str, float] = Field(default_factory=dict)
    expected: list[ExpectedVerdict]

    @model_validator(mode="after")
    def valid_truth(self) -> Truth:
        if set(self.nutrition_per_100) - (set(NUTRIENT_KEYS) - {"other"}):
            raise ValueError("Use canonical nutrient keys in nutrition_per_100")
        if set(self.nutrition_rounding) - set(self.nutrition_per_100):
            raise ValueError("Rounding annotations require an expected nutrient value")
        if any(
            value < 0
            for value in (
                *self.nutrition_per_100.values(),
                *self.nutrition_rounding.values(),
            )
        ):
            raise ValueError(
                "Nutrition truth and rounding tolerances must be nonnegative"
            )
        if set(self.allergen_statements) - {
            "contains",
            "may_contain",
            "facility",
            "free_from",
        }:
            raise ValueError("Unknown allergen statement type")
        ids = [item.eval_profile for item in self.expected]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate evaluation profile IDs")
        return self


def _ingredient_evidence(ingredients: list[Ingredient]) -> list[Evidence]:
    return [
        e
        for ingredient in ingredients
        for e in (
            ingredient.evidence + _ingredient_evidence(ingredient.sub_ingredients)
        )
    ]


def score_packet(truth: Truth, scan: ScanResult) -> PacketScores:
    ingredients = [
        item.name
        for item in scan.extraction.ingredients
        if item.readability != "unreadable"
    ]
    hits = matched_ingredients(truth.ingredients, ingredients)
    reports = {report.profile_id: report.overall for report in scan.reports}
    pairs: list[tuple[VerdictState, VerdictState]] = [
        (expected.state, reports.get(expected.eval_profile, "unknown"))
        for expected in truth.expected
    ]
    nutrition = (
        scan.nutrition_analysis.per_100
        if scan.nutrition_analysis
        and scan.nutrition_analysis.per_100_unit == truth.nutrition_per_100_unit
        else {}
    )
    nutrient_correct = sum(
        key in nutrition
        and math.isfinite(nutrition[key])
        and abs(nutrition[key] - amount)
        <= max(abs(amount) * 0.02, truth.nutrition_rounding.get(key, 0.0)) + 1e-12
        for key, amount in truth.nutrition_per_100.items()
    )
    expected_statements = {
        (kind, normalize(item))
        for kind, items in truth.allergen_statements.items()
        for item in items
    }
    actual_statements = {
        (statement.type, normalize(item))
        for statement in scan.extraction.allergen_statements
        for item in statement.items
    }
    evidence = _ingredient_evidence(scan.extraction.ingredients)
    evidence += [
        e
        for statement in scan.extraction.allergen_statements
        for e in statement.evidence
    ]
    evidence += [e for claim in scan.extraction.claims for e in claim.evidence]
    if scan.extraction.veg_mark.evidence:
        evidence.append(scan.extraction.veg_mark.evidence)
    if scan.extraction.nutrition:
        evidence += [
            value.evidence
            for row in scan.extraction.nutrition.rows
            for value in row.values
            if value.evidence
        ]
    # Count an evidence record once, even when it supports several fields.
    unique = {item.model_dump_json(): item for item in evidence}.values()
    return PacketScores(
        ingredient_matches=hits,
        ingredients_expected=len(truth.ingredients),
        ingredients_predicted=len(ingredients),
        nutrient_correct=nutrient_correct,
        nutrients_expected=len(truth.nutrition_per_100),
        statements_exact=expected_statements == actual_statements,
        veg_mark_correct=truth.veg_mark == scan.extraction.veg_mark.value,
        verdict_pairs=pairs,
        missing_profiles=[
            item.eval_profile
            for item in truth.expected
            if item.eval_profile not in reports
        ],
        evidence_verified=sum(e.status == "verified" for e in unique),
        evidence_total=len(unique),
        unknown_results=sum(
            result.state == "unknown"
            for report in scan.reports
            for result in report.results
        ),
        total_results=sum(len(report.results) for report in scan.reports),
        latency_ms=scan.extraction.meta.duration_ms
        if truth.source == "real" and scan.extraction.meta.duration_ms > 0
        else None,
    )


def run(dataset: Path, responses: Path, reports: Path) -> dict[str, object]:
    truth_files = sorted(
        path
        for path in dataset.glob("*/truth.json")
        if not path.parent.name.startswith("_")
    )
    if not truth_files:
        raise ValueError(
            "No real packet truth files or explicit synthetic packets found; the template is excluded. No accuracy report generated."
        )
    packets: list[PacketRecord] = []
    sources: set[str] = set()
    for path in truth_files:
        truth = Truth.model_validate_json(path.read_text(encoding="utf-8"))
        sources.add(truth.source)
        scan = ScanResult.model_validate_json(
            (responses / f"{path.parent.name}.json").read_text(encoding="utf-8")
        )
        packets.append(
            PacketRecord(packet_id=path.parent.name, **score_packet(truth, scan))
        )
    if len(sources) != 1:
        raise ValueError(
            "Do not mix real and synthetic packets; generate separate reports"
        )
    kind = next(iter(sources))
    scores = score_verdicts(
        [pair for packet in packets for pair in packet["verdict_pairs"]]
    )

    def rate(numerator: CountKey, denominator: CountKey) -> float | None:
        return ratio(
            sum(packet[numerator] for packet in packets),
            sum(packet[denominator] for packet in packets),
        )

    latencies = [
        packet["latency_ms"] for packet in packets if packet["latency_ms"] is not None
    ]
    limitations = [
        "Synthetic fixtures test software behavior only; they do not measure real-packet accuracy."
        if kind == "synthetic"
        else "Human-supplied truth and photo provenance have not been independently verified by the runner.",
        "Nutrient tolerance is max(2% of truth, annotated absolute printed rounding); no unannotated rounding allowance.",
        "Statements use exact normalized item sets; ingredients use top-level items with one-to-one fuzzy matching >=85.",
        "Missing expected profiles count as unknown and are listed; missing responses abort the run.",
        "Evidence rate counts unique extraction evidence records, including nested ingredients, claims and veg marks.",
        "Unknown rate uses restriction results in supplied reports. Verdict accuracy uses expected profile overalls.",
        "Latency uses positive saved extraction durations for real packets only; synthetic latency is unmeasured.",
        "Saved responses are scored as supplied; the runner does not re-evaluate them.",
    ]
    metrics: dict[str, object] = dict(
        dataset_kind=kind,
        packets=len(packets),
        real_packets=len(packets) if kind == "real" else 0,
        ingredient_precision=rate("ingredient_matches", "ingredients_predicted"),
        ingredient_recall=rate("ingredient_matches", "ingredients_expected"),
        nutrient_accuracy=rate("nutrient_correct", "nutrients_expected"),
        statement_accuracy=sum(packet["statements_exact"] for packet in packets)
        / len(packets),
        veg_mark_accuracy=sum(packet["veg_mark_correct"] for packet in packets)
        / len(packets),
        verdict_accuracy=ratio(scores.correct, scores.total),
        confusion_matrix=scores.confusion,
        dangerous_misses=scores.dangerous_misses,
        expected_conflicts=scores.expected_conflicts,
        dangerous_miss_rate=ratio(scores.dangerous_misses, scores.expected_conflicts),
        evidence_verified_rate=rate("evidence_verified", "evidence_total"),
        unknown_rate=rate("unknown_results", "total_results"),
        missing_profile_count=sum(
            len(packet["missing_profiles"]) for packet in packets
        ),
        average_latency_ms=sum(latencies) / len(latencies) if latencies else None,
        latency_samples=len(latencies),
        limitations=limitations,
    )
    reports.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("metrics.json", metrics),
        ("report.json", dict(metrics=metrics, packets=packets)),
    ):
        (reports / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    title = (
        "Synthetic pipeline check — NOT real-packet accuracy"
        if kind == "synthetic"
        else "Real-packet saved-response evaluation"
    )
    lines = [f"# {title}", "", "| Metric | Value |", "| --- | --- |"]
    lines += [
        f"| {key} | {value} |"
        for key, value in metrics.items()
        if key not in {"confusion_matrix", "limitations"}
    ]
    lines += [
        "",
        "Confusion matrix (rows expected, columns predicted):",
        "",
        "```json",
        json.dumps(scores.confusion, indent=2),
        "```",
        "",
    ]
    lines += [f"- {limitation}" for limitation in limitations]
    (reports / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=HERE / "dataset")
    parser.add_argument("--reports", type=Path, default=HERE / "reports")
    args = parser.parse_args()
    try:
        metrics = run(args.dataset, args.responses, args.reports)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Evaluation failed: {error}\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
