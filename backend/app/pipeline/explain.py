"""/api/explain: knowledge base first; otherwise a short, clearly marked LLM explanation (§6)."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend.app import engine_adapter, errors
from backend.app.llm.base import PROSE_PROVIDERS
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.pipeline.textnorm import norm
from backend.app.wording import AI_EXPLANATION_NOTE, LANGUAGE_NAMES, has_banned_word
from shared.contract import ExplainResponse, Lang, Origin

PROMPTS = Path(__file__).resolve().parents[1] / "llm" / "prompts"
CACHE_SIZE = 512
TIMEOUT_S = 12.0


class LLMExplanation(BaseModel):
    display_name: str
    description: str
    origin: Origin
    categories: list[str]
    caution: Optional[str] = None


class LLMTranslation(BaseModel):
    description: str
    caution: Optional[str] = None


class ExplainCache:
    def __init__(self, size: int = CACHE_SIZE) -> None:
        self._items: OrderedDict[tuple[str, Lang], ExplainResponse] = OrderedDict()
        self._size = size

    def get(self, term: str, lang: Lang) -> ExplainResponse | None:
        item = self._items.get((norm(term), lang))
        if item is not None:
            self._items.move_to_end((norm(term), lang))
        return item

    def put(self, term: str, lang: Lang, response: ExplainResponse) -> None:
        self._items[(norm(term), lang)] = response
        self._items.move_to_end((norm(term), lang))
        while len(self._items) > self._size:
            self._items.popitem(last=False)


EXPLAIN_CACHE = ExplainCache()


async def _translate(kb: ExplainResponse, lang: Lang, router: LLMRouter) -> ExplainResponse:
    prompt = ((PROMPTS / "translate.md").read_text(encoding="utf-8")
              .replace("{language}", LANGUAGE_NAMES[lang])
              .replace("{description}", kb.description).replace("{caution}", kb.caution or "none"))
    result = await router.generate(lambda _: prompt, [], LLMTranslation, timeout_s=TIMEOUT_S,
                                   providers=PROSE_PROVIDERS)
    caution = result.value.caution if kb.caution and result.value.caution else kb.caution
    return kb.model_copy(update={"description": result.value.description.strip(), "caution": caution})


async def _from_llm(term: str, lang: Lang, router: LLMRouter) -> ExplainResponse:
    vocabulary = engine_adapter.category_vocabulary()
    prompt = ((PROMPTS / "explain.md").read_text(encoding="utf-8")
              .replace("{term}", term.strip()).replace("{language}", LANGUAGE_NAMES[lang])
              .replace("{categories}", ", ".join(vocabulary)))
    value = (await router.generate(lambda _: prompt, [], LLMExplanation, timeout_s=TIMEOUT_S,
                                   providers=PROSE_PROVIDERS)).value
    caution = " ".join(c for c in (value.caution, AI_EXPLANATION_NOTE[lang]) if c)
    description = value.description.strip()
    if has_banned_word(description):
        raise errors.ApiError(503, "LLM_UNAVAILABLE", "We could not explain this term right now.")
    return ExplainResponse(
        term=term, display_name=value.display_name.strip() or term, description=description,
        origin=value.origin, categories=[c for c in dict.fromkeys(value.categories) if c in vocabulary],
        source="llm", caution=caution,
    )


async def explain(term: str, lang: Lang, router: LLMRouter) -> ExplainResponse:
    cached = EXPLAIN_CACHE.get(term, lang)
    if cached is not None:
        return cached
    kb = engine_adapter.explain_term(term, lang)
    try:
        if kb is not None:
            response = kb if lang == "en" else await _translate(kb, lang, router)
        else:
            response = await _from_llm(term, lang, router)
    except AllProvidersFailedError as exc:
        if kb is not None:
            return kb                            # English KB text beats no answer; not cached
        raise errors.ApiError(503, "LLM_UNAVAILABLE", "This term is not in our database and the AI explainer "
                              "is unavailable right now.", exc.retry_after_s) from exc
    EXPLAIN_CACHE.put(term, lang, response)
    return response
