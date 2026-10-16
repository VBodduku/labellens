"""Degraded mode when every LLM fails: keyword rules over OCR tokens only (spec §4.9).

Ingredients and statements found here are `partial` and every section is `complete=False`, so the engine
can never answer "Not listed" from an OCR-only reading. Nutrition values are usable only when the label
backs them up (ocr_nutrition.py).
"""
from __future__ import annotations

import re
import statistics
from collections.abc import Sequence

from backend.app.pipeline.align import PanelExtraction, line_evidence, split_lines
from backend.app.pipeline.ocr_nutrition import find_nutrition
from backend.app.pipeline.textnorm import clean_item_text, compact, norm, parse_percentage
from shared.contract import (
    AllergenStatement,
    Ingredient,
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
NAME_MIN_HEIGHT = 3.0           # a product name is printed at least this x the photo's usual text height
NAME_MIN_CONFIDENCE = 0.9
NAME_MAX_WORDS = 4
_NOT_A_NAME = re.compile(r"net|weight|quantity|mrp|price|tax|date|batch|lot|useby|bestbefore|mfg|pkd|fssa|lic|"
                         r"ingredient|nutrition|allergen|contains|storage|manufactured|marketed")


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


def product_name(tokens: Sequence[OcrToken]) -> str | None:
    """The brand or product line: printed far larger than the rest, read confidently, words only. Back
    labels rarely have one (their largest print is the price or net-weight box), and then there is none."""
    if not tokens:
        return None
    usual = statistics.median(t.box.h for t in tokens)
    candidates = [
        line for line in split_lines(tokens)
        if statistics.median(t.box.h for t in line) >= NAME_MIN_HEIGHT * usual
        and min(t.confidence for t in line) >= NAME_MIN_CONFIDENCE
        and len(line) <= NAME_MAX_WORDS
        and not any(c.isdigit() for t in line for c in t.text)
        and len(compact(" ".join(t.text for t in line))) >= 3
        and not _NOT_A_NAME.search(compact(" ".join(t.text for t in line)))
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda line: statistics.median(t.box.h for t in line))
    return clean_item_text(" ".join(t.text for t in best))


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
