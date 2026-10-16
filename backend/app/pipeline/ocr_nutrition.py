"""Nutrition table from OCR words alone (OCR-only mode): rows, columns and which numbers can be trusted.

Columns come from the table header ("Per 100 g | Per serve (20 g) | %RDA"); %RDA numbers are dropped.
A row's label may sit anywhere on a printed line, because many packs print the ingredients and the
table side by side. Every number starts as `partial`. It becomes `clear` (usable for verdicts) only
when the label itself backs it up:
  * the column's energy agrees with 4 x protein + 4 x carbohydrate + 9 x fat (within 10 %), which
    clears those four values, and other values in that column that OCR read with high confidence;
  * or its per-100 and per-serving values agree through the printed serving size, which clears both.
A lone number that nothing corroborates stays `partial`, and the engine never decides on it.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from backend.app.pipeline.align import line_evidence, split_lines
from backend.app.pipeline.textnorm import compact, norm, parse_number
from shared.contract import Basis, NutrientRow, NutrientValue, NutritionTable, OcrToken

_UNIT = re.compile(r"^(kcal|kj|mg|mcg|µg|g)\b", re.IGNORECASE)
_LABEL_UNIT = re.compile(r"\b(kcal|kj|mg|mcg|g)\b")
_NUMBER_TOKEN = re.compile(r"^[<~]?\d")
_SMUDGED = ("?", "？", "�")        # a value printed but not readable still occupies its column
_PER_100 = re.compile(r"(?<![\d.])100\s*(g|ml)\b")
_SERVING_SIZE = re.compile(r"serv\w*\s*size\s*(\d+(?:\.\d+)?)\s*(g|ml)\b")
_BRACKETED_SIZE = re.compile(r"\(\s*(\d+(?:\.\d+)?)\s*(g|ml)\s*\)")
_NUTRIENT_LABELS: list[tuple[str, str, str]] = [   # (normalised label prefix, key, default unit)
    ("added sugar", "added_sugars_g", "g"),
    ("total sugar", "total_sugars_g", "g"),
    ("totalsugar", "total_sugars_g", "g"),
    ("sugar", "total_sugars_g", "g"),
    ("saturated fat", "saturated_fat_g", "g"),
    ("saturated", "saturated_fat_g", "g"),
    ("trans fat", "trans_fat_g", "g"),
    ("trans", "trans_fat_g", "g"),
    ("total fat", "total_fat_g", "g"),
    ("totalfat", "total_fat_g", "g"),
    ("fat", "total_fat_g", "g"),
    ("energy", "energy_kcal", "kcal"),
    ("calories", "energy_kcal", "kcal"),
    ("protein", "protein_g", "g"),
    ("carbohydrate", "carbohydrate_g", "g"),
    ("cholesterol", "cholesterol_mg", "mg"),
    ("sodium", "sodium_mg", "mg"),
    ("dietary fib", "fibre_g", "g"),
    ("fibre", "fibre_g", "g"),
    ("fiber", "fibre_g", "g"),
]
_CORE = ("energy_kcal", "protein_g", "carbohydrate_g", "total_fat_g")
ENERGY_MAX_DEVIATION = 0.10     # stricter than the engine's 15 %: here the check decides what is read at all
PAIR_MAX_DEVIATION = 0.10       # per-serving vs per-100 x serving size
PAIR_ROUNDING = 0.1             # absolute allowance for printed rounding of small values
CONFIDENT_TOKEN = 0.9           # OCR confidence for a non-core value in a column that passed the energy check
MAX_GAP_TOKENS = 1              # tokens allowed between the label words and the first number ("(g)")
COLUMN_GAP = 1.5                # x gap (x word height) that separates a side-by-side ingredients column
# Part <= whole on one basis: a value read with high confidence but larger than its whole is a misread.
_PARTS = (("added_sugars_g", "total_sugars_g"), ("added_sugars_g", "carbohydrate_g"),
          ("total_sugars_g", "carbohydrate_g"), ("fibre_g", "carbohydrate_g"),
          ("saturated_fat_g", "total_fat_g"), ("trans_fat_g", "total_fat_g"))
KJ_PER_KCAL = 4.184


@dataclass
class _Cell:
    value: NutrientValue
    confidence: float


@dataclass
class _Row:
    key: str
    label: str
    cells: list[_Cell]


def _number_index(line: Sequence[OcrToken], start: int) -> int | None:
    return next((n for n in range(start, len(line)) if _NUMBER_TOKEN.match(line[n].text)), None)


def _in_list(line: Sequence[OcrToken], n: int) -> bool:
    """Word n is part of a comma-separated ingredient list, not the start of a table row."""
    if line[n].text.rstrip().endswith(","):
        return True
    if n == 0 or not line[n - 1].text.rstrip().endswith(","):
        return False
    gap = line[n].box.x - (line[n - 1].box.x + line[n - 1].box.w)
    return gap < COLUMN_GAP * line[n].box.h


def _label_at(line: Sequence[OcrToken], n: int) -> tuple[str, str, str] | None:
    text = norm(" ".join(t.text for t in line[n:]))
    return next((m for m in _NUTRIENT_LABELS if text.startswith(m[0])), None)


def _cells(line: Sequence[OcrToken], start: int, key: str, unit: str, columns: Sequence[Basis]) -> list[_Cell]:
    """Numbers after the label, one per column in order; %RDA values and anything past the columns are dropped."""
    cells: list[_Cell] = []
    n = start
    while n < len(line) and len(cells) < len(columns):
        token = line[n]
        if "%" in token.text or not (_NUMBER_TOKEN.match(token.text) or any(m in token.text for m in _SMUDGED)):
            n += 1
            continue
        span = [token]
        unit_match = _UNIT.search(re.sub(r"^[<~]?[\d.,Oo]+\s*", "", token.text))
        if unit_match is None and n + 1 < len(line) and _UNIT.match(line[n + 1].text):
            span.append(line[n + 1])
            unit_match = _UNIT.match(line[n + 1].text)
        amount = None if any(m in token.text for m in _SMUDGED) else parse_number(token.text)
        printed = unit_match.group(1).lower() if unit_match else None
        energy_unit = printed in ("kcal", "kj")
        cells.append(_Cell(NutrientValue(
            basis=columns[len(cells)], amount=amount,
            unit=("kJ" if printed == "kj" else printed) if printed and energy_unit == (key == "energy_kcal") else unit,
            raw_text=" ".join(t.text for t in span), evidence=line_evidence(span, 1.0)[0],
            readability="partial" if amount is not None else "unreadable",
        ), token.confidence))
        n += len(span)
    return cells


@dataclass(frozen=True)
class _Label:
    key: str
    text: str           # as printed, e.g. "Sodium (mg)"
    unit: str
    first_number: int   # index of the row's first number on the line


def _find_label(line: Sequence[OcrToken]) -> _Label | None:
    """The row's label: the first nutrient word on the line that is not inside an ingredient list,
    followed closely by a number. A later word ("Fat" in "Trans Fat (o) 0.0") is never tried instead."""
    for n in range(len(line)):
        match = _label_at(line, n)
        if match is None or _in_list(line, n):
            continue
        first = _number_index(line, n)
        if first is None or first - n > len(match[0].split()) + MAX_GAP_TOKENS:
            return None
        text = " ".join(t.text for t in line[n:first])
        unit = match[2]
        if match[1] == "energy_kcal" and "kj" in norm(text) and "kcal" not in norm(text):
            unit = "kJ"
        elif match[1] != "energy_kcal" and (found := _LABEL_UNIT.search(norm(text))):
            unit = found.group(1)
        return _Label(match[1], text, unit, first)
    return None


def _columns(header: str) -> tuple[list[Basis], float | None, str | None]:
    """Column bases in printed order, and the serving size, from the table header."""
    serving = _SERVING_SIZE.search(norm(header)) or _BRACKETED_SIZE.search(header.lower())
    per_100 = _PER_100.search(norm(header))
    columns: list[Basis] = []
    if per_100:
        columns.append("per_100ml" if per_100.group(1) == "ml" else "per_100g")
    # "RDA per serving" names the %RDA column, not a per-serving amount column.
    if serving or any("serv" in w and "rda" not in w for w in map(compact, header.split())):
        columns.append("per_serving")
    return columns or ["per_serving"], float(serving.group(1)) if serving else None, \
        serving.group(2) if serving else None


def _plausible(key: str, value: NutrientValue, column: dict[str, float]) -> bool:
    assert value.amount is not None
    if value.basis in ("per_100g", "per_100ml") and value.unit.lower() == "g" and value.amount > 100:
        return False
    return all(value.amount <= column[whole] for part, whole in _PARTS if part == key and whole in column)


def _amounts(rows: Sequence[_Row], basis: Basis) -> dict[str, float]:
    found: dict[str, float] = {}
    for row in rows:
        for cell in row.cells:
            value = cell.value
            if value.basis == basis and value.amount is not None and row.key not in found:
                found[row.key] = value.amount / KJ_PER_KCAL if value.unit.lower() == "kj" else value.amount
    return found


def _energy_agrees(amounts: dict[str, float]) -> bool:
    if not all(key in amounts for key in _CORE) or amounts["energy_kcal"] <= 0:
        return False
    computed = 4 * amounts["protein_g"] + 4 * amounts["carbohydrate_g"] + 9 * amounts["total_fat_g"]
    return abs(computed - amounts["energy_kcal"]) / amounts["energy_kcal"] <= ENERGY_MAX_DEVIATION


def _pair_agrees(per_100: float, per_serving: float, serving_size: float) -> bool:
    expected = per_100 * serving_size / 100
    return abs(per_serving - expected) <= max(PAIR_MAX_DEVIATION * expected, PAIR_ROUNDING)


def _trusted(rows: Sequence[_Row], columns: Sequence[Basis], serving_size: float | None,
             serving_unit: str | None) -> set[tuple[str, Basis]]:
    trusted: set[tuple[str, Basis]] = set()
    for basis in columns:
        column = _amounts(rows, basis)
        if _energy_agrees(column):
            trusted.update((key, basis) for key in _CORE)
            trusted.update((row.key, basis) for row in rows for cell in row.cells
                           if cell.value.basis == basis and cell.confidence >= CONFIDENT_TOKEN
                           and cell.value.amount is not None and _plausible(row.key, cell.value, column))
    per_100 = next((b for b in columns if b in ("per_100g", "per_100ml")), None)
    if per_100 and serving_size and serving_unit and per_100.endswith(serving_unit) and "per_serving" in columns:
        hundred, serving = _amounts(rows, per_100), _amounts(rows, "per_serving")
        for key in hundred.keys() & serving.keys():
            if _pair_agrees(hundred[key], serving[key], serving_size):
                trusted.update({(key, per_100), (key, "per_serving")})
    return trusted


def find_nutrition(tokens: Sequence[OcrToken]) -> NutritionTable | None:
    """Nutrient rows below the "Nutrition" heading (or anywhere when the photo has none)."""
    heading = next((n for n, t in enumerate(tokens) if compact(t.text).startswith("nutrition")), 0)
    lines = split_lines(tokens[heading:])
    found = [(line, label) for line in lines if (label := _find_label(line)) is not None]
    if not found:
        return None
    first = lines.index(found[0][0])
    columns, serving_size, serving_unit = _columns(" ".join(t.text for line in lines[:first] for t in line))
    rows: list[_Row] = []
    for line, label in found:
        if label.key in {r.key for r in rows}:
            continue
        cells = _cells(line, label.first_number, label.key, label.unit, columns)
        if cells:
            rows.append(_Row(label.key, label.text, cells))
    trusted = _trusted(rows, columns, serving_size, serving_unit)
    return NutritionTable(
        serving_size=serving_size,
        serving_unit="ml" if serving_unit == "ml" else "g" if serving_unit else None,
        rows=[NutrientRow(key=row.key, raw_label=row.label, values=[
            c.value.model_copy(update={"readability": "clear"})
            if (row.key, c.value.basis) in trusted and c.value.amount is not None else c.value
            for c in row.cells]) for row in rows],
    )
