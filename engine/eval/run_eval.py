"""Score saved ScanResult JSON against human truth; no network or synthetic accuracy claims."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict
from shared.contract import Evidence, ScanResult, VerdictState
from engine.eval.metrics import matched_ingredients, ratio, score_verdicts
from engine.normalize import normalize

HERE = Path(__file__).resolve().parent

CountKey = Literal["ingredient_matches", "ingredients_expected", "ingredients_predicted", "nutrient_correct",
                   "nutrients_expected", "evidence_verified", "evidence_total", "unknown_results", "total_results"]


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
    latency_ms: int


class PacketRecord(PacketScores):
    packet_id: str


class ExpectedVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eval_profile: str
    state: VerdictState


class Truth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: str
    ingredients: list[str]
    ingredients_complete_in_photos: bool
    allergen_statements: dict[str, list[str]]
    veg_mark: Literal["veg", "non_veg", "not_found", "unclear"]
    nutrition_per_100: dict[str, float]
    expected: list[ExpectedVerdict]


def score_packet(truth: Truth, scan: ScanResult) -> PacketScores:
    ingredients = [item.name for item in scan.extraction.ingredients if item.readability != "unreadable"]
    hits = matched_ingredients(truth.ingredients, ingredients)
    reports = {report.profile_id: report.overall for report in scan.reports}
    pairs: list[tuple[VerdictState, VerdictState]] = [(expected.state, reports.get(expected.eval_profile, "unknown")) for expected in truth.expected]
    nutrition = scan.nutrition_analysis.per_100 if scan.nutrition_analysis else {}
    nutrient_correct = sum(key in nutrition and math.isfinite(nutrition[key]) and
                           abs(nutrition[key] - amount) <= max(abs(amount) * .02, .05)
                           for key, amount in truth.nutrition_per_100.items())
    expected_statements = {(kind, normalize(item)) for kind, items in truth.allergen_statements.items() for item in items}
    actual_statements = {(statement.type, normalize(item)) for statement in scan.extraction.allergen_statements for item in statement.items}
    evidence: list[Evidence] = [evidence for ingredient in scan.extraction.ingredients for evidence in ingredient.evidence]
    evidence += [evidence for statement in scan.extraction.allergen_statements for evidence in statement.evidence]
    if scan.extraction.nutrition:
        evidence += [value.evidence for row in scan.extraction.nutrition.rows for value in row.values if value.evidence]
    return PacketScores(
        ingredient_matches=hits, ingredients_expected=len(truth.ingredients), ingredients_predicted=len(ingredients),
        nutrient_correct=nutrient_correct, nutrients_expected=len(truth.nutrition_per_100),
        statements_exact=expected_statements == actual_statements,
        veg_mark_correct=truth.veg_mark == scan.extraction.veg_mark.value,
        verdict_pairs=pairs, missing_profiles=[item.eval_profile for item in truth.expected if item.eval_profile not in reports],
        evidence_verified=sum(e.status == "verified" for e in evidence), evidence_total=len(evidence),
        unknown_results=sum(result.state == "unknown" for report in scan.reports for result in report.results),
        total_results=sum(len(report.results) for report in scan.reports), latency_ms=scan.extraction.meta.duration_ms,
    )


def run(dataset: Path, responses: Path, reports: Path) -> dict[str, object]:
    truth_files = sorted(path for path in dataset.glob("*/truth.json") if not path.parent.name.startswith("_"))
    if not truth_files:
        raise ValueError("No real packet truth files found; the template is excluded. No accuracy report generated.")
    packets: list[PacketRecord] = []
    for path in truth_files:
        truth = Truth.model_validate_json(path.read_text(encoding="utf-8"))
        saved = responses / f"{path.parent.name}.json"
        scan = ScanResult.model_validate_json(saved.read_text(encoding="utf-8"))
        packets.append(PacketRecord(packet_id=path.parent.name, **score_packet(truth, scan)))
    scores = score_verdicts([pair for packet in packets for pair in packet["verdict_pairs"]])

    def rate(numerator: CountKey, denominator: CountKey) -> float | None:
        return ratio(sum(packet[numerator] for packet in packets), sum(packet[denominator] for packet in packets))

    limitations = ["Nutrient tolerance: max(2%, 0.05 canonical units); printed rounding is not annotated yet.",
                  "Statements are scored as exact normalized item sets, not semantic aliases.",
                  "Ingredient scoring currently uses top-level extraction items.",
                  "Missing evaluation profiles count as unknown and are listed per packet.",
                  "Saved responses are scored as supplied; the runner does not re-evaluate them."]
    metrics: dict[str, object] = dict(
        packets=len(packets), real_packet_validation="human-supplied truth; provenance not independently verified",
        ingredient_precision=rate("ingredient_matches", "ingredients_predicted"),
        ingredient_recall=rate("ingredient_matches", "ingredients_expected"),
        nutrient_accuracy=rate("nutrient_correct", "nutrients_expected"),
        statement_accuracy=sum(packet["statements_exact"] for packet in packets) / len(packets),
        veg_mark_accuracy=sum(packet["veg_mark_correct"] for packet in packets) / len(packets),
        verdict_accuracy=ratio(scores.correct, scores.total), confusion_matrix=scores.confusion,
        dangerous_misses=scores.dangerous_misses, expected_conflicts=scores.expected_conflicts,
        dangerous_miss_rate=ratio(scores.dangerous_misses, scores.expected_conflicts),
        evidence_verified_rate=rate("evidence_verified", "evidence_total"),
        unknown_rate=rate("unknown_results", "total_results"),
        average_latency_ms=sum(packet["latency_ms"] for packet in packets) / len(packets),
        limitations=limitations,
    )
    reports.mkdir(parents=True, exist_ok=True)
    for name, data in (("metrics.json", metrics), ("report.json", dict(metrics=metrics, packets=packets))):
        (reports / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Saved-response evaluation", "", "| Metric | Value |", "| --- | --- |"]
    lines += [f"| {key} | {value} |" for key, value in metrics.items() if key not in {"confusion_matrix", "limitations"}]
    lines += ["", "Confusion matrix (rows expected, columns predicted):", "", "```json", json.dumps(scores.confusion, indent=2), "```", ""]
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
