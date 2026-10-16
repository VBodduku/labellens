"""Degraded mode when every LLM fails: keyword rules over OCR tokens only (spec §4.9).

Everything found here is `partial` and every section is `complete=False`, so the engine can never
answer "Not listed" from an OCR-only reading.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from backend.app.pipeline.align import PanelExtraction, line_evidence, split_lines
from backend.app.pipeline.textnorm import clean_item_text, compact, norm, parse_number, parse_percentage
from shared.contract import (
    AllergenStatement,
    Ingredient,
    NutrientRow,
    NutrientValue,
    NutritionTable,
    OcrToken,
    SectionPresence,
    SectionStatus,
    StatementType,
    VegMark,
)

ISSUE = "ocr_only"
PARTIAL_CONFIDENCE = 0.6
_INGREDIENT_HEADING = re.compile(r"^(ingredients?|ingredents|सामग्री|पदार्थ|సామగ్రి|పదార్థాలు|కావలసినవి)", re.IGNORECASE)
_STOP_HEADINGS = ("contains", "maycontain", "allergen", "nutrition", "mfd", "manufactured", "marketed",
                  "bestbefore", "storage", "netwt", "netweight")
_UNIT = re.compile(r"^(kcal|kj|mg|mcg|µg|g)\b", re.IGNORECASE)
_NUTRIENT_LABELS: list[tuple[str, str, str]] = [   # (normalised label prefix, key, default unit)
    ("added sugar", "added_sugars_g", "g"),
    ("total sugar", "total_sugars_g", "g"),
    ("sugar", "total_sugars_g", "g"),
    ("saturated", "saturated_fat_g", "g"),
    ("trans", "trans_fat_g", "g"),
    ("total fat", "total_fat_g", "g"),
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


def _section(presence: SectionPresence) -> SectionStatus:
    return SectionStatus(presence=presence, complete=False, issues=[ISSUE])


def _is_stop(token: OcrToken) -> bool:
    return compact(token.text).startswith(_STOP_HEADINGS)


def _depth_after(depth: int, text: str) -> int:
    """Bracket depth after a token. A token ending in ")," / ")." closes everything: OCR often
    garbles brackets ("[Soy])" read as "[Soyl)"), and a stuck depth would swallow the whole label."""
    if re.search(r"[)\]][,.;]?$", text.rstrip()):
        return 0
    return max(0, depth + text.count("(") + text.count("[") - text.count(")") - text.count("]"))


def _ingredient(tokens: list[OcrToken], text: str, n: int) -> Ingredient:
    cleaned = clean_item_text(text).rstrip(".").strip()
    return Ingredient(
        id=f"ing_{n}", raw_text=cleaned, name=cleaned, percentage=parse_percentage(cleaned),
        evidence=line_evidence(tokens, 1.0), readability="partial", confidence=PARTIAL_CONFIDENCE,
    )


def find_ingredients(tokens: Sequence[OcrToken]) -> tuple[list[Ingredient], bool]:
    """Ingredients after an "Ingredients" heading, split on top-level commas, up to the next
    heading or sentence-ending full stop. Returns (ingredients, heading_found)."""
    start = next((n for n, t in enumerate(tokens) if _INGREDIENT_HEADING.match(norm(t.text))), None)
    if start is None:
        return [], False
    ingredients: list[Ingredient] = []
    current: list[OcrToken] = []
    parts: list[str] = []
    remainder = tokens[start].text.split(":", 1)[1] if ":" in tokens[start].text else ""
    if remainder.strip():
        current, parts = [tokens[start]], [remainder]
    depth = _depth_after(0, remainder)

    def flush() -> None:
        if current and compact(" ".join(parts)):
            ingredients.append(_ingredient(list(current), " ".join(parts), len(ingredients)))
        current.clear()
        parts.clear()

    for token in tokens[start + 1:]:
        if _is_stop(token):
            break
        current.append(token)
        parts.append(token.text)
        depth = _depth_after(depth, token.text)
        text = token.text.rstrip()
        if depth == 0 and text.endswith("."):
            flush()
            break
        if depth == 0 and text.endswith((",", ";")):
            flush()
    flush()
    return ingredients, True


def _statement_type(words: str) -> StatementType | None:
    if words.startswith("contains"):
        return "contains"
    if words.startswith("may contain"):
        return "may_contain"
    return None


def find_statements(tokens: Sequence[OcrToken]) -> list[AllergenStatement]:
    statements: list[AllergenStatement] = []
    n = 0
    while n < len(tokens):
        kind = _statement_type(norm(" ".join(t.text for t in tokens[n:n + 2])))
        if kind is None:
            n += 1
            continue
        end = n
        while end < len(tokens) - 1 and not tokens[end].text.rstrip().endswith("."):
            end += 1
        span = list(tokens[n:end + 1])
        text = " ".join(t.text for t in span)
        body = re.split(r"(?i)contains?:?|traces of", text)[-1]
        items = [i.strip(" .") for i in re.split(r",|\band\b|&", body) if i.strip(" .")]
        statements.append(AllergenStatement(
            id=f"alg_{len(statements)}", type=kind, raw_text=text.strip(), items=items,
            evidence=line_evidence(span, 1.0),
        ))
        n = end + 1
    return statements


def _row_values(line: list[OcrToken], label_end: int, default_unit: str, per_100: bool) -> list[NutrientValue]:
    values: list[NutrientValue] = []
    n = label_end
    while n < len(line):
        token = line[n]
        if "%" in token.text or (not any(c.isdigit() for c in token.text) and "?" not in token.text):
            n += 1
            continue
        span = [token]
        unit_match = _UNIT.search(re.sub(r"^[\d.,?Oo]+\s*", "", token.text))
        if unit_match is None and n + 1 < len(line) and _UNIT.match(line[n + 1].text):
            span.append(line[n + 1])
            unit_match = _UNIT.match(line[n + 1].text)
        amount = parse_number(token.text)
        basis = "per_100g" if per_100 and not values else "per_serving"
        raw = " ".join(t.text for t in span)
        values.append(NutrientValue(
            basis=basis, amount=amount, unit=unit_match.group(1) if unit_match else default_unit, raw_text=raw,
            evidence=line_evidence(span, 1.0)[0], readability="partial" if amount is not None else "unreadable",
        ))
        n += len(span)
    return values


def find_nutrition(tokens: Sequence[OcrToken]) -> NutritionTable | None:
    """Nutrient rows by label; only below a "Nutrition" heading when the photo has one."""
    heading = next((n for n, t in enumerate(tokens) if compact(t.text).startswith("nutrition")), 0)
    tokens = tokens[heading:]
    per_100 = "per 100" in norm(" ".join(t.text for t in tokens))
    rows: list[NutrientRow] = []
    for line in split_lines(tokens):
        line_text = norm(" ".join(t.text for t in line))
        match = next((m for m in _NUTRIENT_LABELS if line_text.startswith(m[0])), None)
        if match is None:
            continue
        label_end = next((n for n, t in enumerate(line) if any(c.isdigit() for c in t.text)), len(line))
        values = _row_values(line, label_end, match[2], per_100)
        if values and match[1] not in {r.key for r in rows}:
            rows.append(NutrientRow(key=match[1], raw_label=" ".join(t.text for t in line[:label_end]), values=values))
    return NutritionTable(rows=rows) if rows else None


def extract_panel(image_id: str, tokens: Sequence[OcrToken]) -> PanelExtraction:
    ingredients, heading = find_ingredients(tokens)
    statements = find_statements(tokens)
    nutrition = find_nutrition(tokens)
    return PanelExtraction(
        image_id=image_id,
        ingredients=ingredients,
        ingredients_section=_section("found" if heading else "not_found"),
        allergen_statements=statements,
        allergen_section=_section("found" if statements else "not_found"),
        nutrition=nutrition,
        nutrition_section=_section("found" if nutrition else "not_found"),
        veg_mark=VegMark(value="unclear"),
        claims=[],
    )
