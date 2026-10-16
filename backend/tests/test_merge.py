"""Multi-panel merge rules (spec §4.5)."""
from __future__ import annotations

from backend.app.pipeline.align import PanelExtraction
from backend.app.pipeline.merge import merge_panels
from shared.contract import (
    AllergenStatement,
    Box,
    Claim,
    Evidence,
    EvidenceStatus,
    Ingredient,
    NutrientRow,
    NutrientValue,
    NutritionTable,
    SectionPresence,
    SectionStatus,
    VegMark,
    VegMarkValue,
)


def ev(image_id: str, text: str, status: EvidenceStatus = "verified", score: float = 0.95) -> Evidence:
    box = Box(x=0.1, y=0.1, w=0.1, h=0.02) if status != "unverified" else None
    return Evidence(image_id=image_id, text=text, box=box, status=status, match_score=score)


def ing(image_id: str, name: str, subs: list[Ingredient] | None = None) -> Ingredient:
    return Ingredient(id="x", raw_text=name, name=name, evidence=[ev(image_id, name)], sub_ingredients=subs or [])


def sec(presence: SectionPresence = "found", complete: bool = True, issues: list[str] | None = None) -> SectionStatus:
    return SectionStatus(presence=presence, complete=complete, issues=issues or [])


def value(image_id: str, amount: float | None, basis: str = "per_100g", status: EvidenceStatus = "verified",
          score: float = 0.95) -> NutrientValue:
    return NutrientValue.model_validate({
        "basis": basis, "amount": amount, "unit": "g", "raw_text": f"{amount} g",
        "evidence": ev(image_id, f"{amount} g", status, score),
        "readability": "clear" if amount is not None else "unreadable",
    })


def panel(image_id: str, *, ingredients: list[Ingredient] | None = None, ing_section: SectionStatus | None = None,
          rows: list[NutrientRow] | None = None, statements: list[AllergenStatement] | None = None,
          veg: VegMarkValue = "not_found", claims: list[str] | None = None) -> PanelExtraction:
    return PanelExtraction(
        image_id=image_id,
        ingredients=ingredients or [],
        ingredients_section=ing_section or sec("not_found", False),
        allergen_statements=statements or [],
        allergen_section=sec("found" if statements else "not_found", bool(statements)),
        nutrition=NutritionTable(rows=rows) if rows else None,
        nutrition_section=sec("found" if rows else "not_found", bool(rows)),
        veg_mark=VegMark(value=veg, evidence=ev(image_id, veg, "approximate") if veg != "not_found" else None),
        claims=[Claim(id="c", raw_text=c, evidence=[ev(image_id, c)]) for c in claims or []],
    )


def test_single_panel_passes_through_with_final_ids() -> None:
    p = panel("img_0", ingredients=[ing("img_0", "Sugar"), ing("img_0", "Chocolate", [ing("img_0", "Cocoa")])],
              ing_section=sec(), claims=["High Protein"],
              statements=[AllergenStatement(id="s", type="contains", raw_text="Contains: Milk", items=["Milk"])])
    merged = merge_panels([p])
    assert [i.id for i in merged.ingredients] == ["ing_0", "ing_1"]
    assert merged.ingredients[1].sub_ingredients[0].id == "ing_1_0"
    assert merged.allergen_statements[0].id == "alg_0"
    assert merged.claims[0].id == "clm_0"


def test_most_complete_ingredient_list_wins_and_duplicates_add_evidence() -> None:
    partial = panel("img_0", ingredients=[ing("img_0", "Sugar")], ing_section=sec("partial", False))
    complete = panel("img_1", ingredients=[ing("img_1", "Sugar"), ing("img_1", "Peanuts (22%)")], ing_section=sec())
    merged = merge_panels([partial, complete])
    assert [i.name for i in merged.ingredients] == ["Sugar", "Peanuts (22%)"]
    assert [e.image_id for e in merged.ingredients[0].evidence] == ["img_1", "img_0"]
    assert merged.ingredients_section.complete is True
    assert merged.ingredients_section.issues == []


def test_two_different_partial_lists_keep_best_and_flag_issue() -> None:
    a = panel("img_0", ingredients=[ing("img_0", "Sugar"), ing("img_0", "Peanuts")], ing_section=sec("partial", False))
    b = panel("img_1", ingredients=[ing("img_1", "Cocoa Butter")], ing_section=sec("partial", False))
    merged = merge_panels([a, b])
    assert [i.name for i in merged.ingredients] == ["Sugar", "Peanuts"]
    assert "panels_partial_lists" in merged.ingredients_section.issues
    assert merged.ingredients_section.complete is False


def test_readable_nutrient_value_beats_unreadable() -> None:
    a = panel("img_0", rows=[NutrientRow(key="sodium_mg", raw_label="Sodium", values=[value("img_0", None)])])
    b = panel("img_1", rows=[NutrientRow(key="sodium_mg", raw_label="Sodium", values=[value("img_1", 150)])])
    merged = merge_panels([a, b])
    [row] = merged.nutrition.rows  # type: ignore[union-attr]
    assert row.values[0].amount == 150
    assert merged.nutrition_section.issues == []


def test_disagreeing_values_keep_higher_confidence_and_flag() -> None:
    a = panel("img_0", rows=[NutrientRow(key="total_sugars_g", raw_label="Sugars",
                                         values=[value("img_0", 38.0, status="approximate")])])
    b = panel("img_1", rows=[NutrientRow(key="total_sugars_g", raw_label="Sugars", values=[value("img_1", 36.0)])])
    merged = merge_panels([a, b])
    assert merged.nutrition.rows[0].values[0].amount == 36.0  # type: ignore[union-attr]
    assert "panel_disagreement:total_sugars_g" in merged.nutrition_section.issues


def test_values_within_two_percent_agree() -> None:
    a = panel("img_0", rows=[NutrientRow(key="energy_kcal", raw_label="Energy", values=[value("img_0", 520)])])
    b = panel("img_1", rows=[NutrientRow(key="energy_kcal", raw_label="Energy", values=[value("img_1", 525)])])
    assert merge_panels([a, b]).nutrition_section.issues == []


def test_rows_merge_by_key_and_basis_and_keep_other_labels_apart() -> None:
    a = panel("img_0", rows=[NutrientRow(key="protein_g", raw_label="Protein", values=[value("img_0", 9.5)]),
                             NutrientRow(key="other", raw_label="Salt", values=[value("img_0", 1.2)])])
    b = panel("img_1", rows=[NutrientRow(key="protein_g", raw_label="Protein",
                                         values=[value("img_1", 3.8, basis="per_serving")]),
                             NutrientRow(key="other", raw_label="Calcium", values=[value("img_1", 0.1)])])
    rows = merge_panels([a, b]).nutrition.rows  # type: ignore[union-attr]
    assert [(r.key, r.raw_label) for r in rows] == [("protein_g", "Protein"), ("other", "Salt"), ("other", "Calcium")]
    assert [v.basis for v in rows[0].values] == ["per_100g", "per_serving"]


def test_statements_union_deduplicated_by_type_and_items() -> None:
    def st(image_id: str, kind: str, items: list[str]) -> AllergenStatement:
        return AllergenStatement.model_validate({"id": "s", "type": kind, "raw_text": ", ".join(items),
                                                 "items": items, "evidence": [ev(image_id, "x")]})
    a = panel("img_0", statements=[st("img_0", "contains", ["Milk", "Peanut"])])
    b = panel("img_1", statements=[st("img_1", "contains", ["peanut", "milk"]), st("img_1", "may_contain", ["Milk"])])
    merged = merge_panels([a, b])
    assert [(s.type, len(s.evidence)) for s in merged.allergen_statements] == [("contains", 2), ("may_contain", 1)]


def test_veg_mark_non_veg_wins_then_veg_then_unclear() -> None:
    assert merge_panels([panel("img_0", veg="veg"), panel("img_1", veg="non_veg")]).veg_mark.value == "non_veg"
    assert merge_panels([panel("img_0", veg="unclear"), panel("img_1", veg="veg")]).veg_mark.value == "veg"
    assert merge_panels([panel("img_0", veg="not_found"), panel("img_1", veg="unclear")]).veg_mark.value == "unclear"
    assert merge_panels([panel("img_0"), panel("img_1")]).veg_mark.value == "not_found"


def test_claims_union_deduplicated() -> None:
    merged = merge_panels([panel("img_0", claims=["High Protein"]), panel("img_1", claims=["HIGH PROTEIN", "No palm oil"])])
    assert [c.raw_text for c in merged.claims] == ["High Protein", "No palm oil"]
    assert len(merged.claims[0].evidence) == 2
