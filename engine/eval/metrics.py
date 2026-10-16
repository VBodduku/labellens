"""Offline scoring helpers. Undefined rates are None, never invented perfect scores."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence
from rapidfuzz.fuzz import token_sort_ratio
from engine.normalize import normalize

STATES = ("conflict", "possible", "unknown", "not_listed")


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def matched_ingredients(expected: list[str], predicted: list[str]) -> int:
    """Maximum one-to-one matching prevents duplicate predictions inflating recall."""
    edges = [[j for j, truth in enumerate(expected)
              if token_sort_ratio(normalize(term), normalize(truth)) >= 85] for term in predicted]
    assignment: dict[int, int] = {}

    def augment(index: int, visited: set[int]) -> bool:
        for target in edges[index]:
            if target in visited:
                continue
            visited.add(target)
            if target not in assignment or augment(assignment[target], visited):
                assignment[target] = index
                return True
        return False

    return sum(augment(index, set()) for index in range(len(predicted)))


@dataclass(frozen=True)
class VerdictScores:
    confusion: dict[str, dict[str, int]]
    correct: int
    total: int
    dangerous_misses: int
    expected_conflicts: int


def score_verdicts(pairs: Sequence[tuple[str, str]]) -> VerdictScores:
    matrix = {truth: {prediction: 0 for prediction in STATES} for truth in STATES}
    for truth, prediction in pairs:
        if truth not in STATES or prediction not in STATES:
            raise ValueError("Verdict outside the four-state vocabulary")
        matrix[truth][prediction] += 1
    return VerdictScores(matrix, sum(truth == prediction for truth, prediction in pairs), len(pairs),
                         matrix["conflict"]["not_listed"], sum(matrix["conflict"].values()))
