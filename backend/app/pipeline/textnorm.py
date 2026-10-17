"""Text normalisation for fuzzy matching, and number parsing from printed (OCR) text."""
from __future__ import annotations

import re
import unicodedata

_NON_WORD = re.compile(r"[^\w%]+", re.UNICODE)
_SPACES = re.compile(r"\s+")
_O_AS_ZERO = re.compile(r"(?<=\d)[Oo]|[Oo](?=\d)")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
_THOUSANDS = re.compile(r"^\d{1,3},\d{3}$")
_UNREADABLE_MARKS = ("?", "�")
_UNIT_NAMES = {"kcal": "kcal", "kj": "kJ", "g": "g", "mg": "mg", "mcg": "mcg", "µg": "mcg", "μg": "mcg", "ug": "mcg"}
_UNIT_WORD = re.compile(r"(?<![^\W\d_])(kcal|kj|mcg|µg|μg|ug|mg|g)(?![^\W\d_])", re.IGNORECASE)   # not inside a word


def norm(text: str) -> str:
    """Case-folded, punctuation-free, single-spaced text for comparisons (keeps % and digits)."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return _SPACES.sub(" ", _NON_WORD.sub(" ", text)).strip()


def compact(text: str) -> str:
    return norm(text).replace(" ", "")


def clean_item_text(text: str) -> str:
    """Printed item text without the separator that follows it ("Sugar," -> "Sugar")."""
    return _SPACES.sub(" ", text).strip().rstrip(",;").strip()


def _to_float(raw: str) -> float:
    if _THOUSANDS.match(raw):
        return float(raw.replace(",", ""))
    return float(raw.replace(",", "."))


def parse_number(text: str) -> float | None:
    """First number in printed text; None if there is none or the text is visibly smudged ("1?5")."""
    if any(mark in text for mark in _UNREADABLE_MARKS):
        return None
    match = _NUMBER.search(_O_AS_ZERO.sub("0", text))
    return _to_float(match.group(0)) if match else None


def printed_numbers(text: str) -> list[float]:
    """Every number in printed text except percentages ("MUFA(9) 1.6 5%" -> [9.0, 1.6]); none if smudged."""
    if any(mark in text for mark in _UNREADABLE_MARKS):
        return []
    cleaned = _O_AS_ZERO.sub("0", text)
    return [_to_float(m.group(0)) for m in _NUMBER.finditer(cleaned) if not cleaned[m.end():].lstrip().startswith("%")]


def number_digits(text: str) -> str | None:
    """Digits of the first number in the text, without its decimal point or leading zeros ("08.8" -> "88")."""
    match = _NUMBER.search(_O_AS_ZERO.sub("0", text))
    return (re.sub(r"\D", "", match.group(0)).lstrip("0") or "0") if match else None


def parse_percentage(text: str) -> float | None:
    match = _PERCENT.search(_O_AS_ZERO.sub("0", text))
    return _to_float(match.group(1)) if match else None


def unit_name(unit: str) -> str | None:
    """Canonical nutrient unit ("KCAL" -> "kcal", "µg" -> "mcg"), or None if it is not one."""
    return _UNIT_NAMES.get(unit.strip().casefold())


def printed_units(text: str) -> set[str]:
    """Units written in printed text: "38.0 g" -> {"g"}, "Sodium (mg)" -> {"mg"}, "Sugars" -> set()."""
    return {_UNIT_NAMES[match.group(1).casefold()] for match in _UNIT_WORD.finditer(text)}


def numbers_differ(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) > tolerance * max(abs(a), abs(b), 1e-9)
