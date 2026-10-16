"""Deterministic, span-based matching with compounds taking precedence over shorter aliases."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from rapidfuzz.fuzz import token_sort_ratio
from shared.contract import Ingredient, IngredientAnnotation, Origin
from shared.engine_interface import UnresolvedTerm
from engine.kb_loader import ALIASES, BY_CODE, BY_ID, QUALIFIERS, STATEMENTS, Term
from engine.normalize import code_spans, normalize, split_top_level, unicode_text

# A KB can exceed Python's small implicit regex cache. Keep immutable compiled
# patterns for all aliases so expanding the KB does not compile them per ingredient.
_ALIAS_PATTERNS = tuple(
    (alias, term_id, re.compile(r"(?<!\w)" + re.escape(alias) + r"(?!\w)"))
    for alias, term_id in ALIASES
)


def _word_character(char: str) -> bool:
    # Python's \w excludes combining vowel signs used by Hindi and Telugu.
    # Treat those marks as word content, so a boundary cannot split a syllable.
    return char.isalnum() or char == "_" or unicodedata.category(char).startswith("M")


def _whole_word(text: str, start: int, end: int) -> bool:
    return not (
        (start and _word_character(text[start - 1]))
        or (end < len(text) and _word_character(text[end]))
    )


@dataclass(frozen=True)
class TermMatch:
    entry: Term
    categories: tuple[str, ...]
    possible_categories: tuple[str, ...]
    origin: Origin
    match_type: Literal["code", "exact", "contained", "fuzzy"]
    score: float
    note: str | None = None
    qualifier: str | None = None


@dataclass(frozen=True)
class TextMatches:
    matches: tuple[TermMatch, ...]
    unresolved: tuple[str, ...]


@dataclass(frozen=True)
class IngredientMatches:
    ingredient: Ingredient
    matches: tuple[TermMatch, ...]
    unresolved: tuple[str, ...]


def _resolve(
    entry: Term,
    context: str,
    kind: Literal["code", "exact", "contained", "fuzzy"],
    score: float,
) -> TermMatch:
    categories = list(entry.categories)
    possible = list(entry.possible_categories)
    origin = entry.origin
    note = None
    matched_qualifier = None
    context = normalize(context)
    for qualifier in QUALIFIERS:
        if entry.id not in qualifier.term_ids:
            continue
        matched_qualifier = next(
            (
                phrase
                for phrase in qualifier.phrases
                if _affirmed_phrase(context, phrase)
            ),
            None,
        )
        if matched_qualifier is None:
            continue
        categories.extend(c for c in qualifier.add_categories if c not in categories)
        possible = [
            c
            for c in possible
            if c not in qualifier.remove_categories and c not in categories
        ]
        origin = qualifier.origin
        note = "Source resolved by the printed qualifier."
        break
    return TermMatch(
        entry,
        tuple(categories),
        tuple(possible),
        origin,
        kind,
        score,
        note,
        matched_qualifier,
    )


def _affirmed_phrase(context: str, phrase: str) -> bool:
    for occurrence in re.finditer(
        r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", context
    ):
        before, after = context[: occurrence.start()], context[occurrence.end() :]
        if re.search(r"\b(?:not|no|without|non)\s+(?:(?:of|from)\s+)?$", before):
            continue
        if re.match(r"\s+free\b", after):
            continue
        return True
    return False


# These are label grammar, never ingredient aliases. Unknown content inside a compound
# still survives after recognized spans are removed.
_GRAMMAR = re.compile(
    r"\b(?:ins|e|emulsifiers?|raising agents?|stabili[sz]ers?|preservatives?|colou?r(?:ing)?s?|"
    r"sweeteners?|antioxidants?|acidity regulators?|flavou?r enhancers?|chocolate|ingredients?|"
    r"and|of|from|source|origin|vegetable|plant|microbial|certified|gluten free)\b"
)


def _segment(text: str) -> TextMatches:
    raw = unicode_text(text)
    spans = code_spans(raw)
    matches: list[TermMatch] = []
    unresolved: list[str] = []
    without_codes = list(raw)
    code_ids: set[str] = set()
    for index, span in enumerate(spans):
        entry = BY_CODE.get(span.code)
        # A suffix not explicitly known is never silently collapsed to its parent code.
        if entry is None:
            unresolved.append(raw[span.start : span.end])
        else:
            end = spans[index + 1].start if index + 1 < len(spans) else len(raw)
            context = raw[span.end : end].split(",", 1)[0]
            hit = _resolve(entry, context, "code", 1.0)
            matches.append(hit)
            if hit.qualifier:
                for phrase_match in re.finditer(
                    r"(?<!\w)" + re.escape(hit.qualifier) + r"(?!\w)", context
                ):
                    start, stop = (
                        span.end + phrase_match.start(),
                        span.end + phrase_match.end(),
                    )
                    without_codes[start:stop] = " " * (stop - start)
            else:
                # A negated source phrase is not an independent ingredient declaration.
                for qualifier in QUALIFIERS:
                    if entry.id not in qualifier.term_ids:
                        continue
                    for phrase in qualifier.phrases:
                        for phrase_match in re.finditer(
                            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", context
                        ):
                            if not _affirmed_phrase(normalize(context), phrase):
                                start, stop = (
                                    span.end + phrase_match.start(),
                                    span.end + phrase_match.end(),
                                )
                                without_codes[start:stop] = " " * (stop - start)
            code_ids.add(entry.id)
        without_codes[span.start : span.end] = " " * (span.end - span.start)
    cleaned = normalize("".join(without_codes))
    occupied: list[tuple[int, int]] = []
    for alias, term_id, pattern in _ALIAS_PATTERNS:
        for found in pattern.finditer(cleaned):
            if not _whole_word(cleaned, found.start(), found.end()):
                continue
            if any(
                found.start() < end and start < found.end() for start, end in occupied
            ):
                continue
            occupied.append((found.start(), found.end()))
            if term_id in code_ids:
                continue
            # A qualifier must be attached to this occurrence; a comma begins another item.
            tail = cleaned[found.end() :]
            context = ""
            for piece in re.split(r"[,;]", raw):
                normalized_piece = normalize(piece)
                local_match = pattern.search(normalized_piece)
                if local_match:
                    context = normalized_piece[local_match.end() :]
                    break
            if not tail and not spans:
                context = cleaned
            matches.append(
                _resolve(
                    BY_ID[term_id],
                    context,
                    "exact" if alias == cleaned else "contained",
                    1.0,
                )
            )
    remainder = list(cleaned)
    for start, end in occupied:
        remainder[start:end] = " " * (end - start)
    remaining = " ".join("".join(remainder).split())
    for hit in matches:
        if hit.note:
            for qualifier in QUALIFIERS:
                if hit.entry.id in qualifier.term_ids:
                    for phrase in qualifier.phrases:
                        remaining = re.sub(
                            r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)",
                            " ",
                            remaining,
                        )
    remaining = " ".join(_GRAMMAR.sub(" ", remaining).split())
    if remaining and not spans:
        # OCR often inserts spaces *inside* words. Score a whitespace-repaired
        # candidate as well, retaining the same >=92 threshold and alias length floor.
        candidates = [
            (
                max(
                    token_sort_ratio(cleaned, alias),
                    token_sort_ratio(cleaned.replace(" ", ""), alias.replace(" ", "")),
                ),
                alias,
                term_id,
            )
            for alias, term_id in ALIASES
            if len(alias) >= 5 and len(cleaned) >= 5
        ]
        score, alias, term_id = max(candidates, default=(0.0, "", ""))
        compact_alias = alias.replace(" ", "")
        protects_exact_hits = all(
            cleaned[start:end].replace(" ", "") in compact_alias
            for start, end in occupied
        )
        if (
            score >= 92
            and protects_exact_hits
            and len(alias) > sum(end - start for start, end in occupied)
        ):
            # Compound repair may replace shorter words within that compound
            # (e.g. butter in "co coa butter"), never an unrelated exact allergen.
            return TextMatches(
                (_resolve(BY_ID[term_id], raw, "fuzzy", score / 100),), ()
            )
    # Fuzzy applies to the whole unresolved fragment, never short fragments or arbitrary substrings.
    if remaining:
        candidates = [
            (token_sort_ratio(remaining, alias), alias, term_id)
            for alias, term_id in ALIASES
            if len(alias) >= 5 and len(remaining) >= 5
        ]
        best = max(candidates, default=(0.0, "", ""))
        if best[0] >= 92:
            matches.append(_resolve(BY_ID[best[2]], raw, "fuzzy", best[0] / 100))
        else:
            unresolved.append(remaining)
    if not matches and not unresolved:
        unresolved.append(text.strip())
    # Remove duplicate code/name hits while retaining distinct sources and categories.
    unique: dict[tuple[str, tuple[str, ...], tuple[str, ...]], TermMatch] = {}
    for hit in matches:
        unique.setdefault((hit.entry.id, hit.categories, hit.possible_categories), hit)
    return TextMatches(tuple(unique.values()), tuple(dict.fromkeys(unresolved)))


def match_text(text: str) -> TextMatches:
    parts = split_top_level(text)
    if len(parts) <= 1:
        return _segment(text)
    results = [_segment(part) for part in parts]
    return TextMatches(
        tuple(hit for result in results for hit in result.matches),
        tuple(term for result in results for term in result.unresolved),
    )


def statement_categories(item: str) -> tuple[set[str], set[str]]:
    """(definite, possible) categories of one allergen-statement item ("nuts", "Milk")."""
    definite: set[str] = set()
    possible: set[str] = set()
    for entry in STATEMENTS:
        if normalize(item) in {normalize(name) for name in entry.names}:
            definite.update(entry.categories)
            possible.update(entry.possible_categories)
    if not definite and not possible:
        for hit in match_text(item).matches:
            definite.update(hit.categories)
            possible.update(hit.possible_categories)
    return definite, possible


def match_ingredients(ingredients: list[Ingredient]) -> tuple[IngredientMatches, ...]:
    result: list[IngredientMatches] = []
    for ingredient in ingredients:
        if ingredient.readability == "unreadable":
            result.append(IngredientMatches(ingredient, (), ()))
            result.extend(match_ingredients(ingredient.sub_ingredients))
            continue
        matched = match_text(ingredient.name)
        result.append(
            IngredientMatches(ingredient, matched.matches, matched.unresolved)
        )
        result.extend(match_ingredients(ingredient.sub_ingredients))
    return tuple(result)


def annotation(record: IngredientMatches) -> IngredientAnnotation:
    hits = record.matches
    origins = {hit.origin for hit in hits}
    return IngredientAnnotation(
        ingredient_id=record.ingredient.id,
        canonical_ids=list(dict.fromkeys(hit.entry.id for hit in hits)),
        categories=list(dict.fromkeys(c for hit in hits for c in hit.categories)),
        origin=next(iter(origins))
        if len(origins) == 1
        else "varies"
        if origins
        else "unknown",
        source="kb" if hits else "unresolved",
        note="; ".join(
            dict.fromkeys(
                hit.note or hit.entry.notes
                for hit in hits
                if hit.note or hit.possible_categories
            )
        )
        or None,
    )


def unresolved_terms(records: tuple[IngredientMatches, ...]) -> list[UnresolvedTerm]:
    return [
        UnresolvedTerm(ingredient_id=record.ingredient.id, term=term)
        for record in records
        for term in record.unresolved
    ]
