"""Phase 1 readable-value normalization. Full consistency diagnosis is a Phase 2 task."""
from __future__ import annotations

import math
from shared.contract import ConsistencyCheck, Evidence, LabelExtraction, NutritionAnalysis, NutritionTable
from engine.kb_loader import NUTRIENTS
from engine.normalize import normalize


def readable_values(table: NutritionTable) -> dict[tuple[str, str], tuple[float, Evidence | None]]:
    values: dict[tuple[str, str], tuple[float, Evidence | None]] = {}
    definitions = {item.key: item for item in NUTRIENTS}
    for row in table.rows:
        definition = definitions.get(row.key)
        if definition is None or row.key == "other":
            continue
        for value in row.values:
            if value.amount is None or value.readability != "clear" or not math.isfinite(value.amount) or value.amount < 0:
                continue
            factor = definition.conversions.get(value.unit.lower())
            if factor is None:
                continue
            amount = value.amount * factor
            if row.key == "sodium_mg" and normalize(row.raw_label) in ("salt", "salt equivalent"):
                amount *= .4
            key = (row.key, value.basis)
            # Conflicting duplicate readings must not silently replace one another.
            if key in values and not math.isclose(values[key][0], amount, rel_tol=.02, abs_tol=.001):
                values.pop(key)
                # A later duplicate cannot restore a known inconsistent value.
                values[key] = (float("nan"), None)
            elif key not in values:
                values[key] = (amount, value.evidence)
    return {key: value for key, value in values.items() if math.isfinite(value[0])}


def value_at_basis(table: NutritionTable, nutrient: str, basis: str) -> tuple[float, Evidence | None] | None:
    values = readable_values(table)
    direct = values.get((nutrient, basis))
    if direct is not None:
        return direct
    if table.serving_size and table.serving_size > 0 and table.serving_unit:
        base = "per_100g" if table.serving_unit == "g" else "per_100ml"
        if basis == base and (nutrient, "per_serving") in values:
            amount, evidence = values[(nutrient, "per_serving")]
            return amount * 100 / table.serving_size, evidence
        if basis == "per_serving" and (nutrient, base) in values:
            amount, evidence = values[(nutrient, base)]
            return amount * table.serving_size / 100, evidence
    return None


def analyze_nutrition(extraction: LabelExtraction) -> NutritionAnalysis | None:
    table = extraction.nutrition
    if table is None:
        return None
    values = readable_values(table)
    # Never convert mass to volume without a density supplied by the contract.
    basis = "per_100ml" if any(b == "per_100ml" for _, b in values) or table.serving_unit == "ml" else "per_100g"
    per_100: dict[str, float] = {}
    per_pack: dict[str, float] = {}
    for nutrient in dict.fromkeys(row.key for row in table.rows):
        value = value_at_basis(table, nutrient, basis)
        if value:
            per_100[nutrient] = value[0]
        direct_pack = values.get((nutrient, "per_pack"))
        if direct_pack:
            per_pack[nutrient] = direct_pack[0]
        elif value and table.pack_size and table.pack_size > 0 and table.pack_unit == ("ml" if basis == "per_100ml" else "g"):
            per_pack[nutrient] = value[0] * table.pack_size / 100
        elif table.servings_per_pack and table.servings_per_pack > 0:
            serving = value_at_basis(table, nutrient, "per_serving")
            if serving:
                per_pack[nutrient] = serving[0] * table.servings_per_pack
    return NutritionAnalysis(
        per_100=per_100, per_100_unit="ml" if basis == "per_100ml" else "g", per_pack=per_pack,
        servings_per_pack=table.servings_per_pack,
        consistency=ConsistencyCheck(status="insufficient_data", message_key="nutrition.consistency.insufficient"),
        notes=["nutrition.serving_small"] if table.servings_per_pack and table.servings_per_pack >= 2 else [],
    )
