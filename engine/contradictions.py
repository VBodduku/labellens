"""Contradictions: two readings of the same label that disagree. Deterministic, read-only.

Label vs label: the green veg mark vs a non-vegetarian ingredient or "contains" item, "free from X" vs an
X ingredient, a front-of-pack claim (kb/claims.json) vs the ingredients or nutrition table. AI vs print:
the alignment step records when the model's number differed from the printed one, and the panel merge
records when two photos disagree (both as structured section issues). None of these changes a verdict:
the stricter side is already what the rules use. They are surfaced so the user can check the pack or
correct a misread, with both sides' evidence and the results they touch.

Each has a stable `key` (kind + what it says; ids are only positions). It is `checked` when the user saved that
key in `extraction.checked_contradictions`, or corrected the disputed number (that is how the frontend records
"the pack says this number", and it is what makes the number usable again).
"""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from shared.contract import (
    Claim,
    Contradiction,
    ContradictionKind,
    Evidence,
    Ingredient,
    LabelExtraction,
    ProfileReport,
    VerdictRef,
)
from engine.kb_loader import CLAIMS
from engine.matcher import IngredientMatches, statement_categories
from engine.messages import render
from engine.normalize import normalize

VEG_MARK_CATEGORIES = frozenset({"meat", "poultry", "fish_derived", "egg_derived", "gelatin", "animal_derived"})
AI_VS_PRINT_ISSUE = "llm_ocr_number_mismatch"     # "<issue>:<nutrient>:<basis>:<ai amount>" (backend align)
PANELS_ISSUE = "panel_disagreement"                # "<issue>:<nutrient>:<basis>:<amount>:<amount>" (backend merge)


@dataclass
class Found:
    kind: ContradictionKind
    params: dict[str, str | float]
    evidence: list[Evidence]
    field_path: str | None = None
    ingredient_ids: set[str] = field(default_factory=set)
    terms: set[str] = field(default_factory=set)
    nutrient: str | None = None
    corrected: bool = False     # the disputed number was corrected (or confirmed) by the user


def _evidence(evidence: Sequence[Evidence], text: str, extraction: LabelExtraction) -> list[Evidence]:
    if evidence:
        return list(evidence)
    image_id = extraction.images[0].image_id if extraction.images else "img_0"
    return [Evidence(image_id=image_id, text=text, status="unverified")]


def _paths(ingredients: Sequence[Ingredient], prefix: str = "ingredients") -> Iterator[tuple[str, str]]:
    for index, ingredient in enumerate(ingredients):
        path = f"{prefix}[{index}]"
        yield ingredient.id, path
        yield from _paths(ingredient.sub_ingredients, f"{path}.sub_ingredients")


def _definite(records: Sequence[IngredientMatches]) -> Iterator[tuple[Ingredient, set[str]]]:
    for record in records:
        categories = {c for hit in record.matches for c in hit.categories}
        if categories:
            yield record.ingredient, categories


def _ingredient_side(
    kind: ContradictionKind, ingredient: Ingredient, params: dict[str, str | float], other: list[Evidence],
    extraction: LabelExtraction, paths: dict[str, str],
) -> Found:
    return Found(
        kind, {**params, "term": ingredient.raw_text},
        _evidence(ingredient.evidence, ingredient.raw_text, extraction) + other,
        f"{paths[ingredient.id]}.name", ingredient_ids={ingredient.id}, terms={ingredient.raw_text},
    )


def _veg_mark(extraction: LabelExtraction, records: Sequence[IngredientMatches], paths: dict[str, str]) -> list[Found]:
    if extraction.veg_mark.value != "veg":
        return []
    mark = [extraction.veg_mark.evidence] if extraction.veg_mark.evidence else []
    found = [
        _ingredient_side("veg_mark", ingredient, {"category": "|".join(sorted(hit))}, mark, extraction, paths)
        for ingredient, categories in _definite(records)
        if (hit := categories & VEG_MARK_CATEGORIES)
    ]
    for statement in extraction.allergen_statements:
        if statement.type != "contains":
            continue
        for item in statement.items:
            hit = statement_categories(item)[0] & VEG_MARK_CATEGORIES
            if hit:
                found.append(Found("veg_mark", {"term": item, "category": "|".join(sorted(hit))},
                                   _evidence(statement.evidence, statement.raw_text, extraction) + mark,
                                   terms={item}))
    return found


def _free_from(extraction: LabelExtraction, records: Sequence[IngredientMatches], paths: dict[str, str]) -> list[Found]:
    found: list[Found] = []
    for statement in (s for s in extraction.allergen_statements if s.type == "free_from"):
        side = _evidence(statement.evidence, statement.raw_text, extraction)
        for item in statement.items:
            claimed = statement_categories(item)[0]
            found += [_ingredient_side("free_from", ingredient, {"item": item}, side, extraction, paths)
                      for ingredient, categories in _definite(records) if categories & claimed]
            for contains in (s for s in extraction.allergen_statements if s.type == "contains"):
                found += [Found("free_from", {"item": item, "term": listed},
                                _evidence(contains.evidence, contains.raw_text, extraction) + side, terms={listed})
                          for listed in contains.items if statement_categories(listed)[0] & claimed]
    return found


def _claim_phrase(claim: Claim) -> Iterator[tuple[str, frozenset[str], str | None, float]]:
    text = f" {normalize(claim.raw_text)} "
    for rule in CLAIMS:
        if any(f" {normalize(phrase)} " in text for phrase in rule.phrases):
            yield rule.id, frozenset(rule.categories), rule.nutrient, rule.max_value


def _claims(extraction: LabelExtraction, records: Sequence[IngredientMatches], paths: dict[str, str]) -> list[Found]:
    found: list[Found] = []
    for claim in extraction.claims:
        side = _evidence(claim.evidence, claim.raw_text, extraction)
        for _, categories, nutrient, max_value in _claim_phrase(claim):
            found += [_ingredient_side("claim", ingredient, {"claim": claim.raw_text}, side, extraction, paths)
                      for ingredient, listed in _definite(records) if listed & categories]
            if nutrient and extraction.nutrition:
                for r, row in enumerate(extraction.nutrition.rows):
                    if row.key != nutrient:
                        continue
                    for v, value in enumerate(row.values):
                        if value.amount is not None and value.readability == "clear" and value.amount > max_value:
                            term = f"{row.raw_label} {value.raw_text}".strip()
                            found.append(Found("claim", {"claim": claim.raw_text, "term": term},
                                               _evidence([value.evidence] if value.evidence else [], term, extraction) + side,
                                               f"nutrition.rows[{r}].values[{v}].amount", terms={term}, nutrient=nutrient))
                            break
    return found


def _numbers(extraction: LabelExtraction) -> list[Found]:
    """AI vs print and photo vs photo, from the structured issues the backend records."""
    table = extraction.nutrition
    if table is None:
        return []
    found: list[Found] = []
    for issue in extraction.nutrition_section.issues:
        parts = issue.split(":")
        if parts[0] not in (AI_VS_PRINT_ISSUE, PANELS_ISSUE) or len(parts) < 4:
            continue
        key, basis = parts[1], parts[2]
        for r, row in enumerate(table.rows):
            for v, value in enumerate(row.values):
                if row.key != key or value.basis != basis or value.amount is None:
                    continue
                evidence = _evidence([value.evidence] if value.evidence else [], value.raw_text, extraction)
                path = f"nutrition.rows[{r}].values[{v}].amount"
                try:
                    numbers = [float(p) for p in parts[3:]]
                except ValueError:
                    continue
                corrected = value.corrected_by_user
                if parts[0] == AI_VS_PRINT_ISSUE:
                    found.append(Found("ai_vs_print", {"nutrient": key, "ai_value": numbers[0], "value": value.amount},
                                       evidence, path, nutrient=key, corrected=corrected))
                elif len(numbers) >= 2:
                    other = numbers[1] if numbers[0] == value.amount else numbers[0]
                    found.append(Found("panels", {"nutrient": key, "value": value.amount, "other": other},
                                       evidence, path, nutrient=key, corrected=corrected))
    return found


def _affects(item: Found, reports: Sequence[ProfileReport]) -> list[VerdictRef]:
    refs: list[VerdictRef] = []
    for report in reports:
        for result in report.results:
            touches = any(m.ingredient_id in item.ingredient_ids or m.term in item.terms for m in result.matches) or (
                item.nutrient is not None and result.message_params.get("nutrient") == item.nutrient)
            if touches:
                refs.append(VerdictRef(profile_id=report.profile_id, restriction_id=result.restriction_id))
    return refs


def contradiction_key(kind: ContradictionKind, params: dict[str, str | float]) -> str:
    """Stable identity of a contradiction across rechecks: its kind and what it says."""
    return kind + ":" + "|".join(f"{name}={value}" for name, value in sorted(params.items()))


def find_contradictions(
    extraction: LabelExtraction, records: Sequence[IngredientMatches], reports: Sequence[ProfileReport],
) -> list[Contradiction]:
    paths = dict(_paths(extraction.ingredients))
    found = [*_veg_mark(extraction, records, paths), *_free_from(extraction, records, paths),
             *_claims(extraction, records, paths), *_numbers(extraction)]
    unique: list[Found] = []
    for item in found:
        if not any(u.kind == item.kind and u.params == item.params for u in unique):
            unique.append(item)
    return [
        Contradiction(
            id=f"ctr_{n}", kind=item.kind, message_key=f"contradiction.{item.kind}", message_params=item.params,
            explanation=render(f"contradiction.{item.kind}", item.params), evidence=item.evidence,
            affects=_affects(item, reports), field_path=item.field_path,
            key=(key := contradiction_key(item.kind, item.params)),
            checked=item.corrected or key in extraction.checked_contradictions,
        )
        for n, item in enumerate(unique)
    ]
