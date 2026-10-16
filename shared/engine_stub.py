"""
Deliberately naive stand-in for the real engine (Part 3), so Part 2 can build and test end to end
before the merge. Same function signatures as shared.engine_interface.EngineAPI.

DO NOT improve this file. Real logic belongs in engine/. This gets switched off with ENGINE_MODE=real.
"""
from __future__ import annotations

from typing import Optional

from shared.contract import (
    ConsistencyCheck,
    ExplainResponse,
    IngredientAnnotation,
    LabelExtraction,
    Lang,
    NutritionAnalysis,
    Profile,
    ProfileReport,
    RestrictionCatalogItem,
    RestrictionResult,
    CATEGORIES,
)
from shared.engine_interface import EngineOutput, TermInterpretation

_KEYWORDS: dict[str, list[str]] = {
    "peanut": ["peanut", "groundnut"],
    "tree_nut": ["almond", "cashew", "walnut", "pistachio", "hazelnut"],
    "milk": ["milk", "whey", "casein", "butter", "cream", "lactose"],
    "egg": ["egg", "albumin"],
    "gluten": ["wheat", "barley", "rye", "maida", "atta"],
    "soy": ["soy", "soya"],
    "vegetarian": ["chicken", "meat", "fish", "egg", "gelatin"],
    "jain": ["onion", "garlic", "potato", "carrot", "beetroot", "ginger"],
    "palm_oil": ["palm"],
}

_CATALOG = [
    RestrictionCatalogItem(key="peanut", kind="allergy", label_en="Peanut allergy", default_severity="strict",
                           categories=["peanut"], description_en="Peanuts and groundnut products."),
    RestrictionCatalogItem(key="milk", kind="allergy", label_en="Milk allergy", default_severity="strict",
                           categories=["milk"], description_en="Milk and milk-derived ingredients."),
    RestrictionCatalogItem(key="vegetarian", kind="diet", label_en="Vegetarian (no egg)", default_severity="strict",
                           categories=["meat", "fish_derived", "egg_derived", "gelatin"],
                           description_en="Indian vegetarian: no meat, fish or egg."),
    RestrictionCatalogItem(key="jain", kind="diet", label_en="Jain", default_severity="strict",
                           categories=["meat", "fish_derived", "egg_derived", "gelatin", "onion", "garlic",
                                       "root_vegetable", "honey"],
                           description_en="Vegetarian, plus no onion, garlic, root vegetables or honey."),
]


def evaluate(
    extraction: LabelExtraction,
    profiles: list[Profile],
    interpretations: Optional[dict[str, TermInterpretation]] = None,
) -> EngineOutput:
    reports: list[ProfileReport] = []
    complete = extraction.ingredients_section.complete
    for p in profiles:
        results: list[RestrictionResult] = []
        for r in p.restrictions:
            hits = [
                i for i in extraction.ingredients
                if any(k in i.name.lower() for k in _KEYWORDS.get(r.key, [r.key.replace("_", " ")]))
            ]
            if hits:
                state, key, code = "conflict", "verdict.conflict.ingredient", "CONFLICT_INGREDIENT"
            elif complete:
                state, key, code = "not_listed", "verdict.not_listed.complete", "NOT_LISTED_COMPLETE"
            else:
                state, key, code = "unknown", "verdict.unknown.unreadable", "UNKNOWN_NOT_DETECTED"
            results.append(RestrictionResult(
                restriction_id=r.id, state=state,
                unknown_kind="not_detected" if state == "unknown" else None,
                reason_code=code, message_key=key,
                message_params={"term": hits[0].name if hits else "", "category": r.label},
                explanation=f"[stub] {state} for {r.label}",
                evidence=[e for i in hits for e in i.evidence],
            ))
        order = ["conflict", "possible", "unknown", "not_listed"]
        overall = min((res.state for res in results), key=order.index, default="not_listed")
        reports.append(ProfileReport(profile_id=p.profile_id, overall=overall, results=results))

    return EngineOutput(
        annotations=[IngredientAnnotation(ingredient_id=i.id, source="unresolved") for i in extraction.ingredients],
        nutrition_analysis=analyze_nutrition(extraction),
        reports=reports,
        unknowns=[],
        unresolved_terms=[],
    )


def analyze_nutrition(extraction: LabelExtraction) -> Optional[NutritionAnalysis]:
    if not extraction.nutrition:
        return None
    per_100 = {
        row.key: v.amount
        for row in extraction.nutrition.rows
        for v in row.values
        if v.basis in ("per_100g", "per_100ml") and v.amount is not None
    }
    return NutritionAnalysis(
        per_100=per_100,
        consistency=ConsistencyCheck(status="insufficient_data", message_key="nutrition.consistency.insufficient"),
    )


def explain_term(term: str, lang: Lang = "en") -> Optional[ExplainResponse]:
    return None


def restriction_catalog() -> list[RestrictionCatalogItem]:
    return list(_CATALOG)


def category_vocabulary() -> list[str]:
    return list(CATEGORIES)
