"""
The boundary between Part 2 (backend) and Part 3 (engine). FROZEN with the contract.

Part 3 implements these functions in `engine/__init__.py` with EXACTLY these signatures.
Part 2 calls them through `backend/app/engine_adapter.py`, which picks:
    ENGINE_MODE=stub -> shared.engine_stub   (used until Part 3 is merged)
    ENGINE_MODE=real -> engine               (after merge)

The engine is pure, deterministic Python: no network, no LLM calls, no global mutable state.
When it meets a term it can't resolve from its knowledge base, it returns it in
`unresolved_terms`; Part 2 may ask the LLM to interpret those (constrained to CATEGORIES) and call
`evaluate` again with `interpretations`. LLM-derived matches can never produce more than
"possible" on their own.
"""
from __future__ import annotations

from typing import Optional, Protocol

from pydantic import BaseModel

from shared.contract import (
    Contradiction,
    ExplainResponse,
    IngredientAnnotation,
    LabelExtraction,
    Lang,
    NutritionAnalysis,
    Origin,
    Profile,
    ProfileReport,
    RestrictionCatalogItem,
    UnknownItem,
)


class UnresolvedTerm(BaseModel):
    ingredient_id: str
    term: str


class TermInterpretation(BaseModel):
    term: str
    categories: list[str]           # must be a subset of shared.contract.CATEGORIES
    origin: Origin = "unknown"
    confidence: float               # 0..1, as reported by the model
    rationale: str


class EngineOutput(BaseModel):
    annotations: list[IngredientAnnotation]
    nutrition_analysis: Optional[NutritionAnalysis]
    reports: list[ProfileReport]    # summary fields left empty; Part 2 fills them
    unknowns: list[UnknownItem]
    unresolved_terms: list[UnresolvedTerm]
    contradictions: list[Contradiction] = []    # added with contract 1.0.1


class EngineAPI(Protocol):
    def evaluate(
        self,
        extraction: LabelExtraction,
        profiles: list[Profile],
        interpretations: Optional[dict[str, TermInterpretation]] = None,
    ) -> EngineOutput: ...

    def analyze_nutrition(self, extraction: LabelExtraction) -> Optional[NutritionAnalysis]:
        """Used by Part 2's self-verification loop BEFORE full evaluation."""
        ...

    def explain_term(self, term: str, lang: Lang = "en") -> Optional[ExplainResponse]:
        """Knowledge-base lookup only. Returns None if the term is not in the KB."""
        ...

    def restriction_catalog(self) -> list[RestrictionCatalogItem]: ...

    def category_vocabulary(self) -> list[str]: ...
