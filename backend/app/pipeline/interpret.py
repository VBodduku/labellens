"""LLM interpretation of terms the engine could not resolve (spec §4.7).

Categories are restricted to the engine's vocabulary; the engine caps these signals at "possible".
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend.app import engine_adapter
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from shared.contract import Origin
from shared.engine_interface import TermInterpretation, UnresolvedTerm

logger = logging.getLogger("labellens.interpret")

MAX_TERMS = 16
PROMPT = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "interpret.md"


class LLMTermInterpretation(BaseModel):
    term: str
    categories: list[str]
    origin: Origin = "unknown"
    confidence: float
    rationale: str


class LLMInterpretations(BaseModel):
    interpretations: list[LLMTermInterpretation]


def unique_terms(unresolved: list[UnresolvedTerm]) -> list[str]:
    seen: dict[str, str] = {}
    for item in unresolved:
        key = item.term.strip().casefold()
        if key and key not in seen:
            seen[key] = item.term.strip()
    return list(seen.values())[:MAX_TERMS]


def clean(raw: LLMInterpretations, terms: list[str], vocabulary: list[str]) -> dict[str, TermInterpretation]:
    allowed = set(vocabulary)
    wanted = {t.casefold(): t for t in terms}
    result: dict[str, TermInterpretation] = {}
    for item in raw.interpretations:
        term = wanted.get(item.term.strip().casefold())
        categories = list(dict.fromkeys(c for c in item.categories if c in allowed))
        if term is None or not categories:
            continue
        result[term] = TermInterpretation(
            term=term, categories=categories, origin=item.origin,
            confidence=min(1.0, max(0.0, item.confidence)), rationale=item.rationale.strip()[:200],
        )
    return result


async def interpret(
    unresolved: list[UnresolvedTerm], router: LLMRouter, timeout_s: Optional[float] = None,
) -> dict[str, TermInterpretation] | None:
    """Interpretations by term; None when no model could be asked (so the caller may retry later)."""
    terms = unique_terms(unresolved)
    if not terms:
        return {}
    vocabulary = engine_adapter.category_vocabulary()
    prompt = (PROMPT.read_text(encoding="utf-8")
              .replace("{categories}", ", ".join(vocabulary))
              .replace("{terms}", "\n".join(f"- {t}" for t in terms)))
    try:
        result = await router.generate(lambda _: prompt, [], LLMInterpretations, timeout_s=timeout_s)
    except AllProvidersFailedError:
        logger.warning("interpretation skipped: no LLM available")
        return None
    return clean(result.value, terms, vocabulary)
