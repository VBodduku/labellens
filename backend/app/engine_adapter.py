"""Single entry point to the rules engine: shared.engine_stub (ENGINE_MODE=stub) or engine (real)."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Optional

from backend.app.config import EngineMode, get_settings
from shared.contract import (
    ExplainResponse,
    LabelExtraction,
    Lang,
    NutritionAnalysis,
    Profile,
    RestrictionCatalogItem,
)
from shared.engine_interface import EngineOutput, TermInterpretation

ENGINE_FUNCTIONS = ("evaluate", "analyze_nutrition", "explain_term", "restriction_catalog", "category_vocabulary")


def engine_mode() -> EngineMode:
    return get_settings().engine_mode


def _engine() -> ModuleType:
    if engine_mode() == "stub":
        return importlib.import_module("shared.engine_stub")
    module = importlib.import_module("engine")
    missing = [name for name in ENGINE_FUNCTIONS if not callable(getattr(module, name, None))]
    if missing:
        raise RuntimeError(f"ENGINE_MODE=real but the engine package lacks: {', '.join(missing)}")
    return module


def evaluate(
    extraction: LabelExtraction,
    profiles: list[Profile],
    interpretations: Optional[dict[str, TermInterpretation]] = None,
) -> EngineOutput:
    result: EngineOutput = _engine().evaluate(extraction, profiles, interpretations)
    return result


def analyze_nutrition(extraction: LabelExtraction) -> Optional[NutritionAnalysis]:
    result: Optional[NutritionAnalysis] = _engine().analyze_nutrition(extraction)
    return result


def explain_term(term: str, lang: Lang = "en") -> Optional[ExplainResponse]:
    result: Optional[ExplainResponse] = _engine().explain_term(term, lang)
    return result


def restriction_catalog() -> list[RestrictionCatalogItem]:
    result: list[RestrictionCatalogItem] = _engine().restriction_catalog()
    return result


def category_vocabulary() -> list[str]:
    result: list[str] = _engine().category_vocabulary()
    return result
