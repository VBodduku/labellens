"""Unicode-preserving label normalization; numbers are codes only in additive contexts."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_CODE = r"\d{3,4}[a-f]?(?:\s*\(\s*i{1,3}v?\s*\))?"
_CODES = re.compile(rf"(?<![\w.])(?:(?:ins|e)\s*[-:]?\s*)?({_CODE})(?![\w.%])", re.I)
_ADDITIVE = re.compile(r"\b(?:ins|e\s*\d|emulsifiers?|raising agents?|stabili[sz]ers?|preservatives?|colou?r(?:ing)?s?|sweeteners?|antioxidants?|acidity regulators?|flavou?r enhancers?)\b", re.I)


@dataclass(frozen=True)
class CodeSpan:
    code: str
    start: int
    end: int


def unicode_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().translate(str.maketrans("[]{}", "()()"))


def normalize(text: str) -> str:
    text = unicode_text(text)
    text = re.sub(r"\d+(?:\.\d+)?\s*(?:%|mcg\b|mg\b|kg\b|g\b|ml\b|kcal\b|kj\b)", " ", text)
    # Unicode combining marks are deliberately preserved (Hindi and Telugu).
    text = re.sub(r"[()&,;:/+\-–—.]+", " ", text)
    return " ".join(text.split())


def code_spans(text: str) -> tuple[CodeSpan, ...]:
    text = unicode_text(text)
    result: list[CodeSpan] = []
    context = bool(_ADDITIVE.search(text))
    for match in _CODES.finditer(text):
        raw = match.group(0)
        after = text[match.end():]
        if re.match(r"\s*(?:%|g\b|mg\b|ml\b|kcal\b|kj\b)", after):
            continue
        explicit = bool(re.match(r"(?:ins|e)\s*[-:]?\s*\d", raw))
        bare = text.strip() == raw
        if explicit or context or bare:
            result.append(CodeSpan(re.sub(r"\s+", "", match.group(1)), match.start(), match.end()))
    return tuple(result)


def extract_codes(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(span.code for span in code_spans(text)))


def qualifiers(text: str) -> tuple[str, ...]:
    text = unicode_text(text)
    stack: list[int] = []
    found: list[str] = []
    for index, char in enumerate(text):
        if char == "(":
            stack.append(index + 1)
        elif char == ")" and stack:
            found.append(text[stack.pop():index].strip())
    return tuple(found)


def split_top_level(text: str) -> tuple[str, ...]:
    """Split lists without separating the sub-list inside a compound ingredient."""
    depth, start = 0, 0
    parts: list[str] = []
    for index, char in enumerate(unicode_text(text)):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char in ",;" and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return tuple(part for part in parts if part)
