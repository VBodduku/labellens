"""Merge per-photo extractions into one label (spec §4.5) and assign final contract ids."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz

from backend.app.pipeline.align import PanelExtraction
from backend.app.pipeline.textnorm import norm, numbers_differ
from shared.contract import (
    AllergenStatement,
    Claim,
    Evidence,
    Ingredient,
    NutrientRow,
    NutrientValue,
    NutritionTable,
    SectionStatus,
    VegMark,
    VegMarkValue,
)

DUPLICATE_MIN_SCORE = 90
DISAGREEMENT = 0.02
PARTIAL_LISTS_ISSUE = "panels_partial_lists"
DISAGREEMENT_ISSUE = "panel_disagreement"
_PRESENCE_RANK = {"found": 2, "partial": 1, "not_found": 0}
_STATUS_RANK = {"verified": 2, "approximate": 1, "unverified": 0}
_VEG_PRECEDENCE: list[VegMarkValue] = ["non_veg", "veg", "unclear", "not_found"]


@dataclass
class MergedLabel:
    ingredients: list[Ingredient]
    ingredients_section: SectionStatus
    allergen_statements: list[AllergenStatement]
    allergen_section: SectionStatus
    nutrition: NutritionTable | None
    nutrition_section: SectionStatus
    veg_mark: VegMark
    claims: list[Claim]


def _section_rank(section: SectionStatus) -> tuple[int, int]:
    return int(section.complete), _PRESENCE_RANK[section.presence]


def _verified_count(ingredients: Sequence[Ingredient]) -> int:
    return sum(1 for i in ingredients if any(e.status == "verified" for e in i.evidence))


def _with_issues(section: SectionStatus, issues: Sequence[str]) -> SectionStatus:
    merged = list(dict.fromkeys([*section.issues, *issues]))
    return section.model_copy(update={"issues": merged})


def _same_name(a: str, b: str) -> bool:
    return fuzz.token_sort_ratio(norm(a), norm(b)) >= DUPLICATE_MIN_SCORE


def _flatten(ingredients: Sequence[Ingredient]) -> list[Ingredient]:
    return [x for i in ingredients for x in (i, *_flatten(i.sub_ingredients))]


def _add_evidence(item: Ingredient, others: Sequence[Ingredient]) -> Ingredient:
    extra = [e for o in others if _same_name(item.name, o.name) for e in o.evidence]
    subs = [_add_evidence(s, others) for s in item.sub_ingredients]
    return item.model_copy(update={"evidence": [*item.evidence, *extra], "sub_ingredients": subs})


def merge_ingredients(panels: Sequence[PanelExtraction]) -> tuple[list[Ingredient], SectionStatus]:
    best = max(panels, key=lambda p: (*_section_rank(p.ingredients_section), _verified_count(p.ingredients)))
    others = [i for p in panels if p is not best for i in _flatten(p.ingredients)]
    chosen = [_add_evidence(i, others) for i in best.ingredients]
    chosen_names = [i.name for i in _flatten(best.ingredients)]
    missing = [o for o in others if not any(_same_name(o.name, n) for n in chosen_names)]
    issues = [PARTIAL_LISTS_ISSUE] if missing and not best.ingredients_section.complete else []
    return chosen, _with_issues(best.ingredients_section, issues)


def _value_rank(value: NutrientValue) -> tuple[int, int, float]:
    evidence = value.evidence
    return (
        int(value.amount is not None),
        _STATUS_RANK[evidence.status] if evidence else -1,
        evidence.match_score if evidence else 0.0,
    )


def _merge_values(key: str, values: Sequence[NutrientValue], issues: list[str]) -> NutrientValue:
    readable = [v for v in values if v.amount is not None]
    if any(numbers_differ(a.amount, b.amount, DISAGREEMENT) for a in readable for b in readable
           if a.amount is not None and b.amount is not None):
        issues.append(f"{DISAGREEMENT_ISSUE}:{key}")
    return max(values, key=_value_rank)


def merge_nutrition(panels: Sequence[PanelExtraction]) -> tuple[NutritionTable | None, SectionStatus]:
    tables = [p.nutrition for p in panels if p.nutrition is not None]
    best = max(panels, key=lambda p: (*_section_rank(p.nutrition_section), len(p.nutrition.rows) if p.nutrition else 0))
    section_issues = [i for p in panels for i in p.nutrition_section.issues]
    if not tables:
        return None, _with_issues(best.nutrition_section, section_issues)

    issues: list[str] = []
    rows: dict[str, dict[str, list[NutrientValue]]] = {}
    labels: dict[str, str] = {}
    for table in tables:
        for row in table.rows:
            row_key = row.key if row.key != "other" else f"other:{norm(row.raw_label)}"
            labels.setdefault(row_key, row.raw_label)
            for value in row.values:
                rows.setdefault(row_key, {}).setdefault(value.basis, []).append(value)
    merged_rows = [
        NutrientRow(
            key=row_key.split(":", 1)[0],
            raw_label=labels[row_key],
            values=[_merge_values(row_key.split(":", 1)[0], vals, issues) for vals in by_basis.values()],
        )
        for row_key, by_basis in rows.items()
    ]

    def first(field: str) -> object:
        return next((getattr(t, field) for t in tables if getattr(t, field) is not None), None)

    table = NutritionTable.model_validate({
        "serving_size": first("serving_size"), "serving_unit": first("serving_unit"),
        "servings_per_pack": first("servings_per_pack"), "pack_size": first("pack_size"),
        "pack_unit": first("pack_unit"), "rows": merged_rows,
    })
    return table, _with_issues(best.nutrition_section, [*section_issues, *issues])


def merge_statements(panels: Sequence[PanelExtraction]) -> tuple[list[AllergenStatement], SectionStatus]:
    merged: dict[tuple[str, tuple[str, ...]], AllergenStatement] = {}
    for panel in panels:
        for statement in panel.allergen_statements:
            key = (statement.type, tuple(sorted(norm(i) for i in statement.items)))
            if key in merged:
                existing = merged[key]
                merged[key] = existing.model_copy(update={"evidence": [*existing.evidence, *statement.evidence]})
            else:
                merged[key] = statement
    best = max(panels, key=lambda p: (*_section_rank(p.allergen_section), len(p.allergen_statements)))
    return list(merged.values()), best.allergen_section


def merge_veg_mark(panels: Sequence[PanelExtraction]) -> VegMark:
    marks = [p.veg_mark for p in panels]
    for value in _VEG_PRECEDENCE:
        candidates = [m for m in marks if m.value == value]
        if candidates:
            return next((m for m in candidates if m.evidence is not None), candidates[0])
    return VegMark(value="not_found")


def merge_claims(panels: Sequence[PanelExtraction]) -> list[Claim]:
    merged: dict[str, Claim] = {}
    for claim in (c for p in panels for c in p.claims):
        key = norm(claim.raw_text)
        if key in merged:
            merged[key] = merged[key].model_copy(update={"evidence": [*merged[key].evidence, *claim.evidence]})
        else:
            merged[key] = claim
    return list(merged.values())


def _ingredient_ids(items: Sequence[Ingredient], prefix: str) -> list[Ingredient]:
    return [
        i.model_copy(update={"id": f"{prefix}{n}", "sub_ingredients": _ingredient_ids(i.sub_ingredients, f"{prefix}{n}_")})
        for n, i in enumerate(items)
    ]


def assign_ids(label: MergedLabel) -> MergedLabel:
    label.ingredients = _ingredient_ids(label.ingredients, "ing_")
    label.allergen_statements = [s.model_copy(update={"id": f"alg_{n}"}) for n, s in enumerate(label.allergen_statements)]
    label.claims = [c.model_copy(update={"id": f"clm_{n}"}) for n, c in enumerate(label.claims)]
    return label


def merge_panels(panels: Sequence[PanelExtraction]) -> MergedLabel:
    if not panels:
        raise ValueError("merge_panels needs at least one panel")
    ingredients, ingredients_section = merge_ingredients(panels)
    nutrition, nutrition_section = merge_nutrition(panels)
    statements, allergen_section = merge_statements(panels)
    return assign_ids(MergedLabel(
        ingredients=ingredients,
        ingredients_section=ingredients_section,
        allergen_statements=statements,
        allergen_section=allergen_section,
        nutrition=nutrition,
        nutrition_section=nutrition_section,
        veg_mark=merge_veg_mark(panels),
        claims=merge_claims(panels),
    ))


def evidence_of(label: MergedLabel) -> list[Evidence]:
    """All item evidence (used for the verified-ratio statistics)."""
    items = [e for i in _flatten(label.ingredients) for e in i.evidence]
    items += [e for s in label.allergen_statements for e in s.evidence]
    if label.nutrition:
        items += [v.evidence for r in label.nutrition.rows for v in r.values if v.evidence]
    return items
