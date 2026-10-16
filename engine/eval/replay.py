"""Re-evaluate fixed extractions without inventing the missing LLM interpretation inputs."""

from __future__ import annotations

import math
from pathlib import Path
from pydantic import TypeAdapter
from shared.contract import CATEGORIES, Profile, ScanResult
from shared.engine_interface import TermInterpretation
from engine import evaluate


def load_profiles(path: Path) -> list[Profile]:
    profiles = TypeAdapter(list[Profile]).validate_json(
        path.read_text(encoding="utf-8")
    )
    if not profiles or len({profile.profile_id for profile in profiles}) != len(
        profiles
    ):
        raise ValueError("Evaluation profiles must be nonempty with unique IDs")
    return profiles


def replay(scan: ScanResult, profiles: list[Profile], sidecar: Path) -> ScanResult:
    interpretations: dict[str, TermInterpretation] = {}
    if sidecar.exists():
        interpretations = TypeAdapter(dict[str, TermInterpretation]).validate_json(
            sidecar.read_text(encoding="utf-8")
        )
        if any(
            set(item.categories) - set(CATEGORIES)
            or not math.isfinite(item.confidence)
            or not 0 <= item.confidence <= 1
            for item in interpretations.values()
        ):
            raise ValueError(
                f"{sidecar.name}: interpretations need valid categories and finite confidence within 0..1"
            )
    output = evaluate(scan.extraction, profiles, interpretations)
    llm_ids = {
        item.ingredient_id
        for item in scan.annotations
        if item.source == "llm_interpretation"
    }
    # A partially KB-resolved ingredient keeps source=kb on its annotation even
    # when an unresolved fragment contributes an LLM signal to a report.
    llm_ids.update(
        match.ingredient_id
        for report in scan.reports
        for result in report.results
        for match in result.matches
        if match.source == "llm_interpretation" and match.ingredient_id
    )
    unresolved_ids = {item.ingredient_id for item in output.unresolved_terms}
    if llm_ids & unresolved_ids:
        raise ValueError(
            f"Original LLM inputs are missing for {sorted(llm_ids & unresolved_ids)}; provide {sidecar.name}. Replay must not silently drop LLM signals"
        )
    result = scan.model_copy(deep=True)
    result.annotations = output.annotations
    result.nutrition_analysis = output.nutrition_analysis
    result.reports = output.reports
    result.unknowns = output.unknowns
    return result
