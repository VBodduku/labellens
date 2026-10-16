"""Enumerate scoring errors; causal attribution requires a recorded human/code review."""

from __future__ import annotations

import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from shared.contract import ScanResult
from engine.eval.metrics import ingredient_pairs
from engine.normalize import normalize

ErrorCategory = Literal["extraction", "kb_gap", "matcher_bug", "rule_bug"]


class ErrorReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: ErrorCategory
    explanation: str = Field(min_length=1)
    regression_test: str | None = None

    @model_validator(mode="after")
    def engine_fix_test(self) -> ErrorReview:
        if not self.explanation.strip():
            raise ValueError("Error explanations cannot be blank")
        if self.category != "extraction" and not (self.regression_test or "").strip():
            raise ValueError(
                "Engine-owned error classifications must name their regression test"
            )
        return self


class EvaluationError(BaseModel):
    error_id: str
    packet_id: str
    check: str
    expected: str | float
    predicted: str | float | None
    dangerous_miss: bool = False
    category: ErrorCategory | Literal["unreviewed"] = "unreviewed"
    explanation: str = "Compare truth, original photo, extraction, and engine signals before assigning a cause."
    regression_test: str | None = None


def errors_for_packet(
    packet_id: str,
    ingredients: list[str],
    nutrient_truth: dict[str, float],
    rounding: dict[str, float],
    unit: str,
    statements: dict[str, list[str]],
    veg_mark: str,
    expected: dict[str, str],
    scan: ScanResult,
    reviews: dict[str, ErrorReview],
) -> list[EvaluationError]:
    errors: list[EvaluationError] = []
    predicted = [
        item.name
        for item in scan.extraction.ingredients
        if item.readability != "unreadable"
    ]
    pairs = ingredient_pairs(ingredients, predicted)
    for index, term in enumerate(ingredients):
        if index not in {truth for truth, _ in pairs}:
            errors.append(
                EvaluationError(
                    error_id=f"{packet_id}:ingredient_missing:{index}",
                    packet_id=packet_id,
                    check="ingredient_missing",
                    expected=term,
                    predicted=None,
                )
            )
    for index, term in enumerate(predicted):
        if index not in {prediction for _, prediction in pairs}:
            errors.append(
                EvaluationError(
                    error_id=f"{packet_id}:ingredient_extra:{index}",
                    packet_id=packet_id,
                    check="ingredient_extra",
                    expected="No extra extracted ingredient",
                    predicted=term,
                )
            )
    nutrition = (
        scan.nutrition_analysis.per_100
        if scan.nutrition_analysis and scan.nutrition_analysis.per_100_unit == unit
        else {}
    )
    for key, amount in nutrient_truth.items():
        value = nutrition.get(key)
        if (
            value is None
            or not math.isfinite(value)
            or abs(value - amount)
            > max(abs(amount) * 0.02, rounding.get(key, 0.0)) + 1e-12
        ):
            errors.append(
                EvaluationError(
                    error_id=f"{packet_id}:nutrient:{key}",
                    packet_id=packet_id,
                    check=key,
                    expected=amount,
                    predicted=value
                    if value is not None and math.isfinite(value)
                    else None,
                )
            )
    gold = {
        (kind, normalize(item))
        for kind, values in statements.items()
        for item in values
    }
    actual = {
        (statement.type, normalize(item))
        for statement in scan.extraction.allergen_statements
        for item in statement.items
    }
    if gold != actual:
        errors.append(
            EvaluationError(
                error_id=f"{packet_id}:statements",
                packet_id=packet_id,
                check="allergen_statements",
                expected=str(sorted(gold)),
                predicted=str(sorted(actual)),
            )
        )
    if veg_mark != scan.extraction.veg_mark.value:
        errors.append(
            EvaluationError(
                error_id=f"{packet_id}:veg_mark",
                packet_id=packet_id,
                check="veg_mark",
                expected=veg_mark,
                predicted=scan.extraction.veg_mark.value,
            )
        )
    reports = {report.profile_id: report.overall for report in scan.reports}
    for profile_id, state in expected.items():
        actual_state = reports.get(profile_id)
        if actual_state != state:
            errors.append(
                EvaluationError(
                    error_id=f"{packet_id}:verdict:{profile_id}",
                    packet_id=packet_id,
                    check=f"verdict:{profile_id}",
                    expected=state,
                    predicted=actual_state,
                    dangerous_miss=state == "conflict" and actual_state == "not_listed",
                )
            )
    for error in errors:
        review = reviews.get(error.error_id)
        if review:
            error.category = review.category
            error.explanation = review.explanation
            error.regression_test = review.regression_test
    return errors
