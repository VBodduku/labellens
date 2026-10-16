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
_OPEN, _CLOSE = "([（［", ")]）］"     # OCR reads some printed brackets as full-width ones
_COLUMN_GAP = 2.5           # horizontal gap, in token heights, that separates side-by-side columns
_LINE_GAP = 1.0             # vertical gap, in token heights, that ends a printed block
NAME_MIN_HEIGHT = 3.0           # a product name is printed at least this x the photo's usual text height
NAME_MIN_CONFIDENCE = 0.9
NAME_MAX_WORDS = 4
_NOT_A_NAME = re.compile(r"net|weight|quantity|mrp|price|tax|date|batch|lot|useby|bestbefore|mfg|pkd|fssa|lic|"
                         r"ingredient|nutrition|allergen|contains|storage|manufactured|marketed")


def _section(presence: SectionPresence) -> SectionStatus:
    return SectionStatus(presence=presence, complete=False, issues=[ISSUE])


def _is_stop(token: OcrToken) -> bool:
    return compact(token.text).startswith(_STOP_HEADINGS)


def _closes_everything(text: str) -> bool:
    """A bracket that ends its word (")" / ")," / ").") closes every open bracket: OCR often garbles brackets
    ("[Soy])" read as "[Soyl)"), and a stuck depth would swallow the whole label."""
    return re.search(r"[)\]）］][,.;]?$", text.rstrip()) is not None


def _ingredient(tokens: list[OcrToken], text: str, n: int) -> Ingredient:
    cleaned = clean_item_text(text).rstrip(".").strip()
    return Ingredient(
        id=f"ing_{n}", raw_text=cleaned, name=cleaned, percentage=parse_percentage(cleaned),
        evidence=line_evidence(tokens, 1.0), readability="partial", confidence=PARTIAL_CONFIDENCE,
    )


def _line(tokens: Sequence[OcrToken], anchor: OcrToken) -> list[OcrToken]:
    return next(line for line in split_lines(tokens) if anchor in line)


def _column(tokens: Sequence[OcrToken], anchor: OcrToken) -> tuple[float, float]:
    """x range of the anchor's printed column: its line's neighbours joined by word-sized gaps."""
    line = _line(tokens, anchor)
    gap = _COLUMN_GAP * anchor.box.h
    at = line.index(anchor)
    left = right = at
    while left > 0 and line[left].box.x - (line[left - 1].box.x + line[left - 1].box.w) <= gap:
        left -= 1
    while right < len(line) - 1 and line[right + 1].box.x - (line[right].box.x + line[right].box.w) <= gap:
        right += 1
    return line[left].box.x, line[right].box.x + line[right].box.w


def _in_column(token: OcrToken, column: tuple[float, float], height: float) -> bool:
    gap = _COLUMN_GAP * height
    return token.box.x < column[1] + gap and token.box.x + token.box.w > column[0] - gap


def _block(tokens: Sequence[OcrToken], n: int) -> list[OcrToken]:
    """The anchor and the tokens after it in its own column, until a blank line ends the block."""
    anchor = tokens[n]
    column = _column(tokens, anchor)
    block, bottom = [anchor], anchor.box.y + anchor.box.h
    for token in tokens[n + 1:]:
        if not _in_column(token, column, anchor.box.h):
            continue
        if token.box.y - bottom > _LINE_GAP * anchor.box.h:
            break
        block.append(token)
        column = (min(column[0], token.box.x), max(column[1], token.box.x + token.box.w))
        bottom = max(bottom, token.box.y + token.box.h)
    return block


def _ingredient_tokens(tokens: Sequence[OcrToken], start: int) -> list[OcrToken]:
    """The list after the heading, from the heading's own column: words of a graphic or panel printed
    beside the list ("THIS BAR / CONTAINS") are not part of it."""
    return _block(tokens, start)[1:]


def find_ingredients(tokens: Sequence[OcrToken]) -> tuple[list[Ingredient], bool]:
    """Ingredients after an "Ingredients" heading, from its own column, split on top-level commas (also inside
    a word: OCR often drops the space after a comma), up to the next heading or the list's final full stop.
    A word hyphenated at a line end is joined again. Returns (ingredients, heading_found)."""
    start = next((n for n, t in enumerate(tokens) if _INGREDIENT_HEADING.match(norm(t.text))), None)
    if start is None:
        return [], False
    ingredients: list[Ingredient] = []
    current: list[OcrToken] = []
    text = ""
    depth = 0

    def flush() -> None:
        nonlocal text
        if current and compact(text):
            ingredients.append(_ingredient(list(current), text, len(ingredients)))
        current.clear()
        text = ""

    remainder = tokens[start].text.split(":", 1)[1] if ":" in tokens[start].text else ""
    words = [(tokens[start], remainder)] if remainder.strip() else []
    words += [(token, token.text) for token in _ingredient_tokens(tokens, start)]
    for token, word in words:
        if token is not tokens[start] and _is_stop(token):
            break
        text = text[:-1] if text.endswith("-") else f"{text} " if text else ""     # "oligosaccha- / rides"
        current.append(token)
        ended = False
        for n, char in enumerate(word):
            if char in _OPEN:
                depth += 1
            elif char in _CLOSE:
                depth = 0 if _closes_everything(word[n:]) else max(0, depth - 1)
            if char in ",;" and depth == 0:
                flush()
                if n < len(word) - 1:
                    current.append(token)
                continue
            text += char
            if char == "." and depth == 0 and not word[n + 1:].strip():
                ended = True
        if ended:
            flush()
            break
    flush()
    return ingredients, True


_ADVICE_HEADING = re.compile(r"^allerg(en|y|ens)(advice|information|info|declaration|statement|warning)?$")
_FACILITY = re.compile(r"^(processed|manufactured|produced|packed|made)(in|on)")
_FACILITY_WORDS = re.compile(r"\b(plant|facility|factory|unit|premises|equipment|machinery|line|also|where)\b")
_CONTAINS = re.compile(r"contains?(?!er|ing)")
_FACILITY_ITEMS = (re.compile(r"(?i)\bwhere\s+(?:other\s+)?(.+?)\s+(?:are|is)\b"),
                   re.compile(r"(?i)\b(?:handles?|process(?:es)?|uses?)\s+(?:other\s+)?(.+)$"))
_SENTENCE_END = re.compile(r"\.(?!\d)")
_MAY_CONTAIN = re.compile(r"(?i)\bmay\s*contain")
_MAX_ITEM_WORDS = 4


def _starts_sentence(tokens: Sequence[OcrToken], n: int) -> bool:
    """Statement wording counts only when it opens a sentence: after a full stop or colon, or at the
    start of a line with its list on the same line. "THIS BAR / CONTAINS" over an ingredient list is a graphic."""
    anchor = tokens[n]
    column = _column(tokens, anchor)
    line = [t for t in _line(tokens, anchor) if _in_column(t, column, anchor.box.h)]
    for prev in reversed(tokens[max(0, n - 12):n]):
        if _in_column(prev, column, anchor.box.h) and prev.box.y + prev.box.h >= anchor.box.y - anchor.box.h:
            if prev.text.rstrip().endswith((".", ":", ";", "!")) or _ADVICE_HEADING.match(compact(prev.text)):
                return True
            merged = len(compact(anchor.text)) > len("contains")     # "CONTAINSMILK,SOY." carries its list
            return prev not in line and (merged or line[-1] is not anchor)
    return True


def _sentences(block: list[OcrToken]) -> list[tuple[str, list[OcrToken]]]:
    """Split a block at full stops and "may contain", keeping the tokens behind each piece.
    Line breaks are kept so a wrapped all-caps list can use them as separators."""
    text = ""
    spans: list[tuple[int, int, OcrToken]] = []
    for line in split_lines(block):
        for m, token in enumerate(line):
            text += ("\n" if text and m == 0 else " " if text else "")
            spans.append((len(text), len(text) + len(token.text), token))
            text += token.text
    cuts = sorted({0, len(text)} | {m.end() for m in _SENTENCE_END.finditer(text)}
                  | {m.start() for m in _MAY_CONTAIN.finditer(text)})
    pieces: list[tuple[str, list[OcrToken]]] = []
    for start, end in zip(cuts, cuts[1:]):
        if text[start:end].strip():
            pieces.append((text[start:end].strip(), [t for s, e, t in spans if s < end and e > start]))
    return pieces


def _statement_type(sentence: str) -> StatementType | None:
    words = re.sub(r"^allerg\w*( (advice|information|info|declaration|statement|warning))? ", "", norm(sentence))
    if _CONTAINS.match(compact(words)):
        return "contains"
    if compact(words).startswith("maycontain"):
        return "may_contain"
    if _FACILITY.match(compact(words)) and _FACILITY_WORDS.search(words):
        return "facility"
    return None


def _items(kind: StatementType, sentence: str) -> list[str]:
    """Printed items, or [] when the text is not a short list (then nothing is claimed)."""
    if kind == "facility":
        match = next((m for p in _FACILITY_ITEMS if (m := p.search(sentence.replace("\n", " ")))), None)
        body = match.group(1) if match else ""
    else:
        body = re.split(r"(?i)contains?\s*:?|traces of", sentence)[-1]
    if body.upper() != body:    # only an all-caps list splits at a wrap: OCR often drops its comma there
        body = body.replace("\n", " ")
    items = [clean_item_text(i).strip(" .:") for i in re.split(r",|;|\band\b|&|\n", body)]
    items = [i for i in items if i]
    if any(len(i.split()) > _MAX_ITEM_WORDS or any(c.isdigit() for c in i) for i in items):
        return []
    return items


def _is_trigger(tokens: Sequence[OcrToken], n: int) -> bool:
    head = compact(" ".join(t.text for t in tokens[n:n + 4]))
    if _ADVICE_HEADING.match(compact(tokens[n].text)):
        return True
    if head.startswith("maycontain") or _FACILITY.match(head):
        return _starts_sentence(tokens, n)
    if _CONTAINS.match(compact(tokens[n].text)):
        return re.match(r"(?i)contains?:", tokens[n].text) is not None or _starts_sentence(tokens, n)
    return False


def find_statements(tokens: Sequence[OcrToken]) -> list[AllergenStatement]:
    """Allergen statements read block by block: a statement starts at "Allergen advice", "Contains" or
    "May contain" wording that opens a sentence, and ends at its full stop or at the end of its own
    column block. A statement whose text is not a short list is left out rather than guessed."""
    statements: list[AllergenStatement] = []
    used: set[str] = set()
    for n, token in enumerate(tokens):
        if token.token_id in used or not _is_trigger(tokens, n):
            continue
        block = _block(tokens, n)
        for sentence, span in _sentences(block):
            kind = _statement_type(sentence)
            if kind is None:
                break
            used.update(t.token_id for t in span)
            items = _items(kind, sentence)
            if items:
                statements.append(AllergenStatement(
                    id=f"alg_{len(statements)}", type=kind, raw_text=" ".join(sentence.split()), items=items,
                    evidence=line_evidence(span, 1.0),
                ))
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
