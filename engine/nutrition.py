"""Normalize printed nutrition values and identify suspect readings without correcting them."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from collections.abc import Mapping

from shared.contract import (
    ConsistencyCheck,
    Evidence,
    LabelExtraction,
    NUTRIENT_KEYS,
    NutrientRow,
    NutritionAnalysis,
    NutritionTable,
)
from engine.kb_loader import NUTRIENTS
from engine.normalize import normalize

ValueMap = dict[tuple[str, str], tuple[float, Evidence | None]]
_CORE = ("energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g")
_POLYOLS = "polyols_g"  # Internal only: the frozen contract uses key=other + raw_label.


@dataclass(frozen=True)
class Readings:
    values: ValueMap
    conflicts: frozenset[str]


def _positive(number: float | None) -> bool:
    return number is not None and math.isfinite(number) and number > 0


def _row_key(row: NutrientRow) -> str:
    label = normalize(row.raw_label)
    if row.key == "other":
        if label in {"salt", "salt equivalent"}:
            return "sodium_mg"
        if label in {"polyols", "polyol", "sugar alcohols", "sugar alcohol"}:
            return _POLYOLS
        # A canonical nutrient key is preferred; exact printed aliases handle other rows.
        return next(
            (definition.key for definition in NUTRIENTS if label in definition.names),
            "other",
        )
    return row.key


def _readings(table: NutritionTable) -> Readings:
    values: ValueMap = {}
    blocked: set[tuple[str, str]] = set()
    definitions = {item.key: item for item in NUTRIENTS}
    for row in table.rows:
        key = _row_key(row)
        definition = definitions.get(key)
        if key != _POLYOLS and (definition is None or key == "other"):
            continue
        for value in row.values:
            amount = value.amount
            if (
                amount is None
                or value.readability != "clear"
                or not math.isfinite(amount)
                or amount < 0
            ):
                continue
            conversions = (
                {"g": 1.0, "mg": 0.001, "mcg": 0.000001}
                if key == _POLYOLS
                else definition.conversions
                if definition
                else {}
            )
            factor = conversions.get(value.unit.strip().lower())
            if factor is None:
                continue
            amount *= factor
            if key == "sodium_mg" and normalize(row.raw_label) in {
                "salt",
                "salt equivalent",
            }:
                amount *= 0.4  # g salt -> mg salt -> mg sodium, i.e. g salt x400.
            if not math.isfinite(amount):
                continue
            pair = (key, value.basis)
            if pair in blocked:
                continue
            if pair in values and not math.isclose(
                values[pair][0], amount, rel_tol=0.02, abs_tol=0.001
            ):
                values.pop(pair)
                blocked.add(pair)
            else:
                values.setdefault(pair, (amount, value.evidence))
    return Readings(values, frozenset(key for key, _ in blocked))


def readable_values(table: NutritionTable) -> ValueMap:
    return _readings(table).values


def _servings(table: NutritionTable) -> float | None:
    if _positive(table.servings_per_pack):
        return table.servings_per_pack
    if (
        _positive(table.pack_size)
        and _positive(table.serving_size)
        and table.pack_unit is not None
        and table.pack_unit == table.serving_unit
    ):
        assert table.pack_size is not None and table.serving_size is not None
        return table.pack_size / table.serving_size
    return None


def _scale(table: NutritionTable, basis: str, unit: str) -> float | None:
    """Quantity represented by a basis, expressed in one unit; no density assumptions."""
    if basis == f"per_100{unit}":
        return 100.0
    if (
        basis == "per_serving"
        and table.serving_unit == unit
        and _positive(table.serving_size)
    ):
        return table.serving_size
    if basis == "per_pack" and table.pack_unit == unit and _positive(table.pack_size):
        return table.pack_size
    return None


def _value_at_basis(
    table: NutritionTable,
    values: Mapping[tuple[str, str], tuple[float, Evidence | None]],
    nutrient: str,
    basis: str,
) -> tuple[float, Evidence | None] | None:
    direct = values.get((nutrient, basis))
    if direct is not None:
        return direct
    for source in ("per_100g", "per_100ml", "per_serving", "per_pack"):
        value = values.get((nutrient, source))
        if value is None:
            continue
        for unit in ("g", "ml"):
            source_size, target_size = (
                _scale(table, source, unit),
                _scale(table, basis, unit),
            )
            if source_size is not None and target_size is not None:
                amount = value[0] * target_size / source_size
                if math.isfinite(amount):
                    return amount, value[1]
        servings = _servings(table)
        if servings and {source, basis} == {"per_serving", "per_pack"}:
            amount = value[0] * (servings if source == "per_serving" else 1 / servings)
            if math.isfinite(amount):
                return amount, value[1]
    return None


def value_at_basis(
    table: NutritionTable, nutrient: str, basis: str
) -> tuple[float, Evidence | None] | None:
    return _value_at_basis(table, readable_values(table), nutrient, basis)


def correction_candidates(number: float) -> tuple[float, ...]:
    """Single-field OCR hypotheses; never written back to extraction or analysis values."""
    candidates = {number * 10, number / 10, number / 100, number / 1000}
    text = format(number, ".12f").rstrip("0").rstrip(".") or "0"
    replacements = {"0": "8", "8": "0", "1": "7", "7": "1", "5": "6", "6": "5"}
    for index, digit in enumerate(text):
        if digit in replacements:
            candidates.add(
                float(text[:index] + replacements[digit] + text[index + 1 :])
            )
    return tuple(
        sorted(
            value
            for value in candidates
            if math.isfinite(value) and value >= 0 and value != number
        )
    )


def _includes_fibre(table: NutritionTable) -> bool:
    return any(
        _row_key(row) == "carbohydrate_g"
        and re.search(
            r"\b(?:including|includes|inclusive of|incl)\s+(?:dietary\s+)?fi(?:bre|ber)\b",
            normalize(row.raw_label),
        )
        for row in table.rows
    )


def _computed(values: Mapping[str, float], includes_fibre: bool) -> float:
    carb = values["carbohydrate_g"] - (
        values.get("fibre_g", 0.0) if includes_fibre else 0.0
    )
    return (
        4 * values["protein_g"]
        + 4 * carb
        + 9 * values["total_fat_g"]
        + 2.4 * values.get(_POLYOLS, 0.0)
    )


def _deviation(declared: float, computed: float) -> float:
    if declared == 0:
        return 0.0 if computed == 0 else math.inf
    return abs(computed - declared) / declared * 100


def _sanity_suspects(table: NutritionTable, values: ValueMap) -> set[str]:
    suspects: set[str] = set()
    keys = set(key for key, _ in values)
    for basis in ("per_100g", "per_100ml", "per_serving", "per_pack"):
        amounts = {
            key: value[0]
            for key in keys
            if (value := _value_at_basis(table, values, key, basis)) is not None
        }
        for part, whole in (
            ("total_sugars_g", "carbohydrate_g"),
            ("saturated_fat_g", "total_fat_g"),
            ("added_sugars_g", "total_sugars_g"),
        ):
            if (
                part in amounts
                and whole in amounts
                and amounts[part] > amounts[whole] + 1e-9
            ):
                # Either side could be the misread value; do not guess which one is correct.
                suspects.update((part, whole))
    if _positive(table.serving_size) and table.serving_unit:
        assert table.serving_size is not None
        for key in keys:
            per_100, serving = (
                values.get((key, f"per_100{table.serving_unit}")),
                values.get((key, "per_serving")),
            )
            if per_100 and serving:
                expected = per_100[0] * table.serving_size / 100
                if _deviation(expected, serving[0]) > 10 + 1e-9:
                    suspects.add(key)
    return suspects


def _consistency(
    table: NutritionTable, readings: Readings, preferred_basis: str
) -> ConsistencyCheck:
    values = readings.values
    suspects = set(readings.conflicts) | _sanity_suspects(table, values)
    amounts: dict[str, float] = {}
    for basis in dict.fromkeys((preferred_basis, "per_serving", "per_pack")):
        amounts = {
            key: value[0]
            for key in (*_CORE, "fibre_g", _POLYOLS)
            if (value := _value_at_basis(table, values, key, basis)) is not None
        }
        if set(_CORE) <= amounts.keys():
            break

    def ordered_suspects() -> list[str]:
        return [key for key in NUTRIENT_KEYS if key in suspects]

    if not set(_CORE) <= amounts.keys():
        return ConsistencyCheck(
            status="insufficient_data",
            suspect_keys=ordered_suspects(),
            message_key="nutrition.consistency.insufficient",
        )
    declared, computed = (
        amounts["energy_kcal"],
        _computed(amounts, _includes_fibre(table)),
    )
    deviation = _deviation(declared, computed)
    energy_mismatch = (
        deviation > 15 + 1e-9 or computed < 0 or not math.isfinite(computed)
    )
    if energy_mismatch:
        plausible: set[str] = set()
        for key in _CORE:
            for candidate in correction_candidates(amounts[key]):
                corrected = dict(amounts)
                corrected[key] = candidate
                corrected_computed = _computed(corrected, _includes_fibre(table))
                if (
                    corrected_computed >= 0
                    and _deviation(corrected["energy_kcal"], corrected_computed) <= 5
                ):
                    plausible.add(key)
                    break
        suspects.update(plausible or _CORE)
    inconsistent = energy_mismatch or bool(suspects)
    return ConsistencyCheck(
        status="inconsistent" if inconsistent else "consistent",
        declared_kcal=declared,
        computed_kcal=computed if math.isfinite(computed) else None,
        deviation_pct=round(deviation, 2) if math.isfinite(deviation) else None,
        suspect_keys=ordered_suspects(),
        message_key="nutrition.consistency.mismatch"
        if inconsistent
        else "nutrition.consistency.ok",
    )


def analyze_nutrition(extraction: LabelExtraction) -> NutritionAnalysis | None:
    table = extraction.nutrition
    if table is None:
        return None
    readings = _readings(table)
    values = readings.values
    printed_bases = {basis for _, basis in values if basis in {"per_100g", "per_100ml"}}
    unit = (
        "ml"
        if printed_bases == {"per_100ml"}
        else "g"
        if printed_bases == {"per_100g"}
        else table.serving_unit or table.pack_unit or "g"
    )
    basis = f"per_100{unit}"
    per_100: dict[str, float] = {}
    per_pack: dict[str, float] = {}
    for nutrient in dict.fromkeys(key for key, _ in values if key in NUTRIENT_KEYS):
        value = _value_at_basis(table, values, nutrient, basis)
        if value is not None:
            per_100[nutrient] = value[0]
        pack = _value_at_basis(table, values, nutrient, "per_pack")
        if pack is not None:
            per_pack[nutrient] = pack[0]
    servings = _servings(table)
    return NutritionAnalysis(
        per_100=per_100,
        per_100_unit=unit,
        per_pack=per_pack,
        servings_per_pack=servings,
        consistency=_consistency(table, readings, basis),
        notes=["nutrition.serving_small"]
        if servings is not None and servings >= 2
        else [],
    )
