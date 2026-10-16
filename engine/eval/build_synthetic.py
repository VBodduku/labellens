"""Create two reproducible fixture-derived cases; no photographs or real accuracy claims."""

from __future__ import annotations

import json
from pathlib import Path

from shared.contract import Profile, ScanResult, VerdictState
from engine import evaluate
from engine.eval.run_eval import ExpectedVerdict, HERE, Truth


def build(output_root: Path = HERE / "synthetic") -> tuple[Path, Path]:
    fixture = ScanResult.model_validate_json(
        (HERE.parent.parent / "shared/fixtures/scan_result.json").read_text(
            encoding="utf-8"
        )
    )
    profiles = [
        Profile.model_validate(item)
        for item in json.loads(
            (HERE / "eval_profiles.json").read_text(encoding="utf-8")
        )
    ]
    # Manual expectations from the fixture, independent of the predictions being scored.
    clean_expected: dict[str, VerdictState] = {
        "peanut": "conflict",
        "milk": "conflict",
        "gluten": "conflict",
        "vegetarian": "not_listed",
        "vegan": "conflict",
        "jain": "possible",
        "diabetes_sugar": "conflict",
        "low_sodium": "unknown",
    }
    imperfect_expected = {
        **clean_expected,
        "peanut": "unknown",
        "vegetarian": "possible",
    }
    dataset, responses = output_root / "dataset", output_root / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    for imperfect in (False, True):
        case_id = "synthetic_imperfect" if imperfect else "synthetic_clean"
        scan = fixture.model_copy(deep=True)
        scan.scan_id = scan.extraction.scan_id = case_id
        scan.extraction.meta.model = "fixture-derived-synthetic-phase2"
        scan.extraction.meta.duration_ms = 0
        if imperfect:
            scan.extraction.ingredients_section.complete = False
            scan.extraction.ingredients_section.issues = [
                "truncated_at_image_edge",
                "unreadable_span",
            ]
            scan.extraction.ingredients[1].readability = "unreadable"
            scan.extraction.ingredients_section.unreadable_regions = list(
                scan.extraction.ingredients[1].evidence
            )
            scan.extraction.allergen_statements = []
            scan.extraction.allergen_section.presence = "not_found"
            scan.extraction.allergen_section.complete = False
            scan.extraction.veg_mark.value = "unclear"
            assert scan.extraction.nutrition is not None
            for row in scan.extraction.nutrition.rows:
                if row.key == "carbohydrate_g":
                    for value in row.values:
                        if value.basis == "per_100g":
                            value.amount = (
                                5.8  # Deliberately corrupt the fixture's 58 g reading.
                            )
                            value.raw_text = "5.8 g"
                            if value.evidence:
                                value.evidence.text = "Carbohydrate 5.8 g"
                                value.evidence.status = "unverified"
                                value.evidence.box = None
                                value.evidence.token_ids = []
        output = evaluate(scan.extraction, profiles)
        scan.annotations = output.annotations
        scan.nutrition_analysis = output.nutrition_analysis
        scan.reports = output.reports
        scan.unknowns = output.unknowns
        assert fixture.nutrition_analysis is not None
        expectations = imperfect_expected if imperfect else clean_expected
        truth = Truth(
            source="synthetic",
            product="Fixture Nuvo Choco Nut Crunch Bar",
            ingredients=[
                ingredient.name for ingredient in fixture.extraction.ingredients
            ],
            ingredients_complete_in_photos=not imperfect,
            allergen_statements={}
            if imperfect
            else {
                statement.type: statement.items
                for statement in fixture.extraction.allergen_statements
            },
            veg_mark="unclear" if imperfect else "veg",
            nutrition_per_100=dict(fixture.nutrition_analysis.per_100),
            nutrition_rounding={
                key: 0.05 for key in fixture.nutrition_analysis.per_100
            },
            expected=[
                ExpectedVerdict(eval_profile=key, state=state)
                for key, state in expectations.items()
            ],
        )
        target = dataset / case_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "truth.json").write_text(
            truth.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (responses / f"{case_id}.json").write_text(
            scan.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    return dataset, responses


if __name__ == "__main__":
    dataset, responses = build()
    print(f"Synthetic truth: {dataset}\nSynthetic saved responses: {responses}")
