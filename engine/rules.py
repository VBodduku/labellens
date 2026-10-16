"""Signals in master-spec table order, then worst-state aggregation. No model verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from shared.contract import (
    CATEGORIES,
    Evidence,
    IngredientAnnotation,
    LabelExtraction,
    Match,
    NutritionAnalysis,
    Profile,
    ProfileReport,
    Restriction,
    RestrictionResult,
    SectionStatus,
    UnknownItem,
    UnknownKind,
    UnknownSection,
    VerdictState,
)
from shared.engine_interface import EngineOutput, TermInterpretation
from engine.kb_loader import BY_KEY, STATEMENTS
from engine.matcher import (
    IngredientMatches,
    annotation,
    match_ingredients,
    match_text,
    unresolved_terms,
)
from engine.messages import render
from engine.normalize import normalize
from engine.nutrition import analyze_nutrition, value_at_basis

_ORDER = {"conflict": 0, "possible": 1, "unknown": 2, "not_listed": 3}
_VEG_RESOLVES = frozenset(
    {"meat", "poultry", "fish_derived", "egg_derived", "gelatin", "animal_derived"}
)


@dataclass
class Signal:
    state: VerdictState
    code: str
    key: str
    params: dict[str, str | float] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)
    confidence: float = 1.0
    unknown_kind: UnknownKind | None = None


def _signal(
    state: VerdictState, code: str, suffix: str, **params: str | float
) -> Signal:
    return Signal(
        state,
        code,
        f"verdict.{state}.{suffix}",
        params,
        unknown_kind="undeterminable" if state == "unknown" else None,
    )


def _evidence(
    evidence: list[Evidence], text: str, extraction: LabelExtraction
) -> list[Evidence]:
    if evidence:
        return list(evidence)
    return [
        Evidence(
            image_id=extraction.images[0].image_id if extraction.images else "img_0",
            text=text,
            status="unverified",
        )
    ]


def _interpretations(
    records: tuple[IngredientMatches, ...],
    interpretations: dict[str, TermInterpretation],
) -> list[tuple[IngredientMatches, TermInterpretation]]:
    resolved: list[tuple[IngredientMatches, TermInterpretation]] = []
    for record in records:
        for term in record.unresolved:
            interpretation = interpretations.get(term) or interpretations.get(
                normalize(term)
            )
            if interpretation is None:
                continue
            # The shared type is permissive; the engine enforces the constrained vocabulary.
            if (
                set(interpretation.categories) - set(CATEGORIES)
                or not math.isfinite(interpretation.confidence)
                or not 0 <= interpretation.confidence <= 1
            ):
                continue
            if normalize(interpretation.term) != normalize(term):
                continue
            resolved.append((record, interpretation))
    return resolved


def _ingredient_signals(
    extraction: LabelExtraction,
    restriction: Restriction,
    categories: set[str],
    records: tuple[IngredientMatches, ...],
    llm: list[tuple[IngredientMatches, TermInterpretation]],
) -> list[Signal]:
    definite: list[Signal] = []
    ambiguous: list[Signal] = []
    interpreted: list[Signal] = []
    sugars: list[Signal] = []
    green = extraction.veg_mark.value == "veg"
    for record in records:
        ingredient = record.ingredient
        evidence = _evidence(ingredient.evidence, ingredient.raw_text, extraction)
        for hit in record.matches:
            matched = categories.intersection(hit.categories)
            possible = categories.intersection(hit.possible_categories)
            resolved_by_mark = possible.intersection(_VEG_RESOLVES) if green else set()
            possible -= resolved_by_mark
            note = hit.note
            if resolved_by_mark:
                note = "Green veg mark resolves slaughter-derived ambiguity only; dairy, honey, insects and Jain plant restrictions remain."
            if matched:
                if restriction.key == "diabetes_sugar":
                    signal = _signal(
                        "possible",
                        "POSSIBLE_SUGAR_ALIAS",
                        "sugar_alias",
                        term=ingredient.raw_text,
                    )
                    target = sugars
                else:
                    signal = _signal(
                        "conflict",
                        "CONFLICT_INGREDIENT",
                        "ingredient",
                        term=ingredient.raw_text,
                        category="|".join(sorted(matched)),
                    )
                    target = definite
                if green and set(hit.categories).intersection(_VEG_RESOLVES):
                    note = "Internally inconsistent label: explicit ingredient conflicts with the green vegetarian mark."
                    signal.evidence.extend(
                        [extraction.veg_mark.evidence]
                        if extraction.veg_mark.evidence
                        else []
                    )
                signal.matches = [
                    Match(
                        ingredient_id=ingredient.id,
                        term=ingredient.raw_text,
                        canonical_id=hit.entry.id,
                        category=c,
                        source="kb",
                        note=note,
                    )
                    for c in sorted(matched)
                ]
                signal.evidence = evidence + signal.evidence
                target.append(signal)
            if possible:
                signal = _signal(
                    "possible",
                    "POSSIBLE_AMBIGUOUS_SOURCE",
                    "ambiguous_source",
                    term=ingredient.raw_text,
                    category="|".join(sorted(possible)),
                )
                signal.confidence = 0.7
                signal.evidence = evidence + (
                    [extraction.veg_mark.evidence]
                    if resolved_by_mark and extraction.veg_mark.evidence
                    else []
                )
                signal.matches = [
                    Match(
                        ingredient_id=ingredient.id,
                        term=ingredient.raw_text,
                        canonical_id=hit.entry.id,
                        category=c,
                        source="kb",
                        note=note or hit.entry.notes,
                    )
                    for c in sorted(possible)
                ]
                ambiguous.append(signal)
            elif resolved_by_mark:
                # This supporting signal never asserts absence in an incomplete section.
                signal = _absence(extraction, categories, records, restriction)
                signal.evidence = evidence + (
                    [extraction.veg_mark.evidence]
                    if extraction.veg_mark.evidence
                    else []
                )
                signal.matches = [
                    Match(
                        ingredient_id=ingredient.id,
                        term=ingredient.raw_text,
                        canonical_id=hit.entry.id,
                        source="kb",
                        note=note,
                    )
                ]
                ambiguous.append(signal)
    for record, interpretation in llm:
        matched = categories.intersection(interpretation.categories)
        if matched:
            signal = _signal(
                "possible",
                "POSSIBLE_LLM_INTERPRETATION",
                "llm_interpretation",
                term=record.ingredient.raw_text,
                category="|".join(sorted(matched)),
            )
            signal.confidence = interpretation.confidence * 0.8
            signal.evidence = _evidence(
                record.ingredient.evidence, record.ingredient.raw_text, extraction
            )
            signal.matches = [
                Match(
                    ingredient_id=record.ingredient.id,
                    term=record.ingredient.raw_text,
                    category=c,
                    source="llm_interpretation",
                    note=interpretation.rationale,
                )
                for c in sorted(matched)
            ]
            interpreted.append(signal)
    return definite + ambiguous + interpreted + sugars


def _statement_signals(
    extraction: LabelExtraction, restriction: Restriction, categories: set[str]
) -> list[Signal]:
    contains: list[Signal] = []
    traces: list[Signal] = []
    for statement in extraction.allergen_statements:
        if statement.type == "free_from":
            continue
        for item in statement.items:
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
            matched = categories.intersection(definite)
            ambiguous = categories.intersection(possible) - matched
            if not matched and not ambiguous:
                continue
            if statement.type == "contains" and matched:
                signal = _signal(
                    "conflict", "CONFLICT_STATEMENT", "statement", item=item
                )
            elif statement.type == "contains":
                signal = _signal(
                    "possible",
                    "POSSIBLE_AMBIGUOUS_SOURCE",
                    "ambiguous_source",
                    term=item,
                    category="|".join(sorted(ambiguous)),
                )
                signal.confidence = 0.7
            elif restriction.severity == "strict":
                code = (
                    "POSSIBLE_MAY_CONTAIN"
                    if statement.type == "may_contain"
                    else "POSSIBLE_FACILITY"
                )
                signal = _signal("possible", code, statement.type, item=item)
            else:
                signal = _signal(
                    "not_listed", "NOT_LISTED_TRACE_NOTE", "trace_note", item=item
                )
            signal.evidence = _evidence(
                statement.evidence, statement.raw_text, extraction
            )
            signal.matches = [
                Match(
                    term=item,
                    category=c,
                    source="allergen_statement",
                    note="Internally inconsistent label: contains statement conflicts with the green vegetarian mark."
                    if statement.type == "contains"
                    and extraction.veg_mark.value == "veg"
                    and definite.intersection(_VEG_RESOLVES)
                    else "Item is ambiguous."
                    if c in ambiguous
                    else None,
                )
                for c in sorted(matched | ambiguous)
            ]
            (contains if statement.type == "contains" else traces).append(signal)
    return contains + traces


def _absence(
    extraction: LabelExtraction,
    categories: set[str],
    records: tuple[IngredientMatches, ...],
    restriction: Restriction,
) -> Signal:
    section = extraction.ingredients_section
    if section.presence == "not_found":
        return _signal("unknown", "UNKNOWN_SECTION_MISSING", "section_missing")
    unreadable = (
        bool(section.unreadable_regions)
        or any(r.ingredient.readability != "clear" for r in records)
        or any("unreadable" in issue for issue in section.issues)
    )
    truncated = section.presence == "partial" or any(
        "truncat" in issue or "cut_off" in issue for issue in section.issues
    )
    if truncated or (not section.complete and not unreadable):
        signal = _signal(
            "unknown",
            "UNKNOWN_TRUNCATED",
            "truncated",
            category="|".join(sorted(categories)),
        )
        signal.unknown_kind = "not_detected"
        return signal
    if unreadable:
        signal = _signal(
            "unknown",
            "UNKNOWN_UNREADABLE",
            "unreadable",
            category="|".join(sorted(categories)),
        )
        signal.unknown_kind = "not_detected"
        signal.evidence = list(section.unreadable_regions)
        return signal
    if (
        restriction.key in {"vegetarian", "eggetarian"}
        and extraction.veg_mark.value == "veg"
    ):
        signal = _signal("not_listed", "NOT_LISTED_VEG_MARK", "veg_mark")
        signal.evidence = (
            [extraction.veg_mark.evidence] if extraction.veg_mark.evidence else []
        )
        return signal
    return _signal("not_listed", "NOT_LISTED_COMPLETE", "complete")


def _threshold_signal(
    extraction: LabelExtraction,
    restriction: Restriction,
    analysis: NutritionAnalysis | None,
) -> Signal | None:
    catalog = BY_KEY[restriction.key]
    threshold = restriction.threshold or catalog.default_threshold
    if not threshold:
        return (
            _signal(
                "unknown",
                "UNKNOWN_NUTRIENT_MISSING",
                "nutrient_missing",
                nutrient="requested nutrient",
            )
            if catalog.needs_threshold
            else None
        )
    if extraction.nutrition is None:
        return _signal("unknown", "UNKNOWN_NUTRITION_MISSING", "nutrition_missing")
    if analysis and threshold.nutrient in analysis.consistency.suspect_keys:
        signal = _signal(
            "unknown",
            "UNKNOWN_SUSPECT_VALUE",
            "suspect_value",
            nutrient=threshold.nutrient,
        )
        signal.evidence = [
            value.evidence
            for row in extraction.nutrition.rows
            if row.key == threshold.nutrient
            for value in row.values
            if value.evidence
        ]
        if not signal.evidence:
            value = value_at_basis(
                extraction.nutrition, threshold.nutrient, threshold.basis
            )
            signal.evidence = [value[1]] if value and value[1] else []
        return signal
    value = value_at_basis(extraction.nutrition, threshold.nutrient, threshold.basis)
    if value is None:
        signal = _signal(
            "unknown",
            "UNKNOWN_NUTRIENT_MISSING",
            "nutrient_missing",
            nutrient=threshold.nutrient,
        )
        signal.evidence = [
            value.evidence
            for row in extraction.nutrition.rows
            if row.key == threshold.nutrient
            for value in row.values
            if value.evidence
        ]
        signal.evidence += [
            region
            for region in extraction.nutrition_section.unreadable_regions
            if region not in signal.evidence
        ]
        return signal
    amount, evidence = value
    conflict = amount > threshold.max_value
    signal = _signal(
        "conflict" if conflict else "not_listed",
        "CONFLICT_THRESHOLD" if conflict else "NOT_LISTED_WITHIN_LIMIT",
        "threshold" if conflict else "within_limit",
        nutrient=threshold.nutrient,
        value=amount,
        unit="kcal"
        if threshold.nutrient.endswith("kcal")
        else "mg"
        if threshold.nutrient.endswith("mg")
        else "g",
        basis=threshold.basis,
        limit=threshold.max_value,
    )
    signal.evidence = _evidence(
        [evidence] if evidence else [], threshold.nutrient, extraction
    )
    signal.matches = [
        Match(
            term=evidence.text if evidence else threshold.nutrient, source="nutrition"
        )
    ]
    return signal


def _aggregate(restriction: Restriction, signals: list[Signal]) -> RestrictionResult:
    ordered = sorted(signals, key=lambda signal: _ORDER[signal.state])
    first = ordered[0]
    evidence: list[Evidence] = []
    for signal in ordered:
        for item in signal.evidence:
            if item not in evidence:
                evidence.append(item)
    confidence = first.confidence
    if evidence and all(item.status == "unverified" for item in evidence):
        confidence = max(0, confidence - 0.2)
    return RestrictionResult(
        restriction_id=restriction.id,
        state=first.state,
        unknown_kind=first.unknown_kind,
        reason_code=first.code,
        message_key=first.key,
        message_params=first.params,
        explanation=render(first.key, first.params),
        evidence=evidence,
        matches=[match for signal in ordered for match in signal.matches],
        confidence=round(confidence, 6),
    )


def _restriction(
    extraction: LabelExtraction,
    restriction: Restriction,
    records: tuple[IngredientMatches, ...],
    llm: list[tuple[IngredientMatches, TermInterpretation]],
    analysis: NutritionAnalysis | None,
) -> RestrictionResult:
    catalog = BY_KEY.get(restriction.key)
    if catalog is None:
        return _aggregate(
            restriction, [_signal("unknown", "UNKNOWN_NOT_ON_LABELS", "not_on_labels")]
        )
    categories = set(catalog.categories)
    signals = _ingredient_signals(extraction, restriction, categories, records, llm)
    signals += (
        _statement_signals(extraction, restriction, categories)
        if restriction.key != "diabetes_sugar"
        else []
    )
    if extraction.veg_mark.value == "non_veg" and categories.intersection(
        _VEG_RESOLVES
    ):
        signal = _signal("conflict", "CONFLICT_VEG_MARK", "veg_mark")
        signal.evidence = _evidence(
            [extraction.veg_mark.evidence] if extraction.veg_mark.evidence else [],
            "Non-vegetarian mark",
            extraction,
        )
        signal.matches = [Match(term="Non-vegetarian mark", source="veg_mark")]
        signals.append(signal)
    threshold_signal = _threshold_signal(extraction, restriction, analysis)
    if threshold_signal:
        signals.append(threshold_signal)
    if not signals or (
        not catalog.needs_threshold and all(s.state == "not_listed" for s in signals)
    ):
        absence = _absence(extraction, categories, records, restriction)
        if not signals or absence.state == "unknown":
            signals.append(absence)
    return _aggregate(restriction, signals)


def unknown_items(extraction: LabelExtraction) -> list[UnknownItem]:
    items: list[UnknownItem] = []
    sections: tuple[tuple[UnknownSection, SectionStatus], ...] = (
        ("ingredients", extraction.ingredients_section),
        ("nutrition", extraction.nutrition_section),
        ("allergens", extraction.allergen_section),
    )
    for name, section in sections:
        for region in section.unreadable_regions:
            items.append(
                UnknownItem(
                    section=name, message_key="unknown.unreadable_span", region=region
                )
            )
    pending = list(extraction.ingredients)
    unreadable = False
    while pending:
        ingredient = pending.pop(0)
        pending.extend(ingredient.sub_ingredients)
        if ingredient.readability != "clear":
            unreadable = True
            regions: list[Evidence | None] = list(ingredient.evidence) or [None]
            for region in regions:
                if region is None or not any(item.region == region for item in items):
                    items.append(
                        UnknownItem(
                            section="ingredients",
                            message_key="unknown.unreadable_span",
                            detail=ingredient.raw_text,
                            region=region,
                        )
                    )
    section = extraction.ingredients_section
    unreadable = (
        unreadable
        or bool(section.unreadable_regions)
        or any("unreadable" in issue for issue in section.issues)
    )
    if (
        section.presence == "partial"
        or any("truncat" in issue or "cut_off" in issue for issue in section.issues)
        or (not section.complete and section.presence != "not_found" and not unreadable)
    ):
        items.append(
            UnknownItem(
                section="ingredients", message_key="unknown.ingredients_truncated"
            )
        )
    if extraction.nutrition:
        for row in extraction.nutrition.rows:
            for value in row.values:
                if value.readability != "clear" or value.amount is None:
                    if value.evidence is None or not any(
                        item.region == value.evidence for item in items
                    ):
                        items.append(
                            UnknownItem(
                                section="nutrition",
                                message_key="unknown.unreadable_span",
                                detail=row.raw_label,
                                region=value.evidence,
                            )
                        )
    if not extraction.allergen_statements:
        items.append(
            UnknownItem(
                section="allergens", message_key="unknown.no_allergen_statement"
            )
        )
    if extraction.veg_mark.value == "unclear":
        items.append(
            UnknownItem(
                section="veg_mark",
                message_key="unknown.veg_mark_unclear",
                region=extraction.veg_mark.evidence,
            )
        )
    return items


def worst(states: Iterable[VerdictState]) -> VerdictState:
    return min(states, key=_ORDER.__getitem__, default="not_listed")


def evaluate(
    extraction: LabelExtraction,
    profiles: list[Profile],
    interpretations: dict[str, TermInterpretation] | None = None,
) -> EngineOutput:
    records = match_ingredients(extraction.ingredients)
    llm = _interpretations(
        records,
        {normalize(key): value for key, value in (interpretations or {}).items()},
    )
    annotations: list[IngredientAnnotation] = [annotation(record) for record in records]
    for item in annotations:
        interpreted = [
            interpretation
            for record, interpretation in llm
            if record.ingredient.id == item.ingredient_id
        ]
        if item.source == "unresolved" and interpreted:
            item.source = "llm_interpretation"
            item.categories = list(
                dict.fromkeys(
                    c
                    for interpretation in interpreted
                    for c in interpretation.categories
                )
            )
            origins = {interpretation.origin for interpretation in interpreted}
            item.origin = next(iter(origins)) if len(origins) == 1 else "varies"
            item.note = "; ".join(
                interpretation.rationale for interpretation in interpreted
            )
    analysis = analyze_nutrition(extraction)
    reports: list[ProfileReport] = []
    for profile in profiles:
        results = [
            _restriction(extraction, restriction, records, llm, analysis)
            for restriction in profile.restrictions
        ]
        reports.append(
            ProfileReport(
                profile_id=profile.profile_id,
                overall=worst(result.state for result in results),
                results=results,
            )
        )
    interpreted_keys = {
        (record.ingredient.id, normalize(interpretation.term))
        for record, interpretation in llm
    }
    return EngineOutput(
        annotations=annotations,
        nutrition_analysis=analysis,
        reports=reports,
        unknowns=unknown_items(extraction),
        unresolved_terms=[
            term
            for term in unresolved_terms(records)
            if (term.ingredient_id, normalize(term.term)) not in interpreted_keys
        ],
    )
