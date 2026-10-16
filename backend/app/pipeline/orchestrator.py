"""The scan flow (master spec §5.1 steps 3-9 and 11).

quality -> cache lookup -> OCR (panels in parallel) -> LLM structuring (Gemini -> backup -> Ollama)
-> alignment -> panel merge -> cache store -> engine -> ScanResult. When every LLM fails or the LLM
budget runs out, the OCR-only reader replaces structuring + alignment.

Phase 3 plugs in here: the self-verification loop runs after the merge, LLM interpretation of
unresolved terms after the first engine evaluation, and per-profile summaries before assembly.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass

from backend.app import engine_adapter, errors
from backend.app.cache import ExtractionCache, cache_key
from backend.app.config import get_settings
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.logging_setup import note, stage
from backend.app.pipeline import ocr_only
from backend.app.pipeline.align import PanelExtraction, TokenIndex, align_panel, panel_image_ids
from backend.app.pipeline.assemble import build_scan_result
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.llm_schema import LLMExtraction
from backend.app.pipeline.merge import MergedLabel, evidence_of, merge_panels
from backend.app.pipeline.ocr import run_ocr
from backend.app.pipeline.quality import add_cropped_edge, assess
from backend.app.pipeline.structure import PROMPT_VERSION, structure
from shared.contract import (
    ExtractionMeta,
    ImageInfo,
    ImageQuality,
    LabelExtraction,
    Lang,
    OcrToken,
    PanelHint,
    Profile,
    Provider,
    ScanResult,
)

SCAN_BUDGET_S = 45.0
POST_LLM_RESERVE_S = 5.0        # time kept for alignment, merge and the engine after the LLM call


@dataclass(frozen=True)
class ScanInput:
    images: list[PreparedImage]
    raw: list[bytes]
    hints: list[PanelHint]
    profiles: list[Profile]
    lang: Lang


@dataclass(frozen=True)
class Structured:
    label: MergedLabel
    provider: Provider
    model: str
    attempts: int
    product_name: str | None = None
    languages: tuple[str, ...] = ()


def new_scan_id() -> str:
    return f"scan_{uuid.uuid4().hex[:12]}"


def _hint(hints: list[PanelHint], n: int) -> PanelHint:
    return hints[n] if n < len(hints) else "unknown"


async def _ocr_all(images: list[PreparedImage]) -> list[list[OcrToken]]:
    return list(await asyncio.gather(*(run_ocr(image) for image in images)))


def _from_llm(extraction: LLMExtraction, images: list[PreparedImage], tokens: list[OcrToken]) -> list[PanelExtraction]:
    image_ids = [i.image_id for i in images]
    panels = extraction.panels[: len(image_ids)]
    index = TokenIndex(tokens)
    return [align_panel(p, image_id, index) for p, image_id in zip(panels, panel_image_ids(panels, image_ids))]


def _ocr_only(images: list[PreparedImage], tokens: list[OcrToken]) -> Structured:
    panels = [ocr_only.extract_panel(i.image_id, [t for t in tokens if t.image_id == i.image_id]) for i in images]
    return Structured(merge_panels(panels), "ocr_only", "rapidocr", 0)


async def _structure(scan: ScanInput, tokens: list[OcrToken], router: LLMRouter, budget_s: float) -> Structured:
    try:
        with stage("llm"):
            result = await asyncio.wait_for(structure(scan.images, scan.hints, tokens, router), budget_s)
    except (AllProvidersFailedError, TimeoutError) as exc:
        note("llm_failure", type(exc).__name__)
        with stage("ocr_only"):
            return _ocr_only(scan.images, tokens)
    with stage("align"):
        panels = _from_llm(result.value, scan.images, tokens)
    with stage("merge"):
        label = merge_panels(panels)
    return Structured(label, result.provider, result.model, result.attempts,
                      result.value.product_name, tuple(result.value.languages))


def _extraction(scan: ScanInput, qualities: list[ImageQuality], tokens: list[OcrToken], s: Structured,
                duration_ms: int) -> LabelExtraction:
    images = [
        ImageInfo(image_id=i.image_id, width=i.width, height=i.height, panel_hint=_hint(scan.hints, n), quality=q)
        for n, (i, q) in enumerate(zip(scan.images, qualities))
    ]
    label = s.label
    return LabelExtraction(
        scan_id=new_scan_id(),
        images=images,
        ocr_tokens=tokens,
        product_name=s.product_name,
        languages_detected=list(s.languages),
        ingredients=label.ingredients,
        ingredients_section=label.ingredients_section,
        nutrition=label.nutrition,
        nutrition_section=label.nutrition_section,
        allergen_statements=label.allergen_statements,
        allergen_section=label.allergen_section,
        veg_mark=label.veg_mark,
        claims=label.claims,
        meta=ExtractionMeta(provider=s.provider, model=s.model, attempts=s.attempts, duration_ms=duration_ms),
    )


async def extract(scan: ScanInput, router: LLMRouter, cache: ExtractionCache) -> LabelExtraction:
    started = time.perf_counter()
    key = cache_key(scan.raw, scan.hints, PROMPT_VERSION, get_settings().gemini_model)
    cached = cache.get(key)
    if cached is not None:
        note("cache_hit", True)
        return cached.model_copy(update={
            "scan_id": new_scan_id(), "meta": cached.meta.model_copy(update={"cache_hit": True}),
        })

    with stage("quality"):
        qualities = [assess(i) for i in scan.images]
    with stage("ocr"):
        per_image = await _ocr_all(scan.images)
    qualities = [add_cropped_edge(q, t) for q, t in zip(qualities, per_image)]
    if not any(per_image) and all(not q.ok for q in qualities):
        raise errors.bad_image("We could not read any text. Retake the photo closer, in good light.")
    tokens = [t for image_tokens in per_image for t in image_tokens]

    budget = SCAN_BUDGET_S - POST_LLM_RESERVE_S - (time.perf_counter() - started)
    structured = await _structure(scan, tokens, router, max(1.0, budget))
    extraction = _extraction(scan, qualities, tokens, structured, int((time.perf_counter() - started) * 1000))

    evidence = evidence_of(structured.label)
    note("provider", structured.provider)
    note("attempts", structured.attempts)
    note("verified_ratio", round(sum(e.status == "verified" for e in evidence) / len(evidence), 3) if evidence else None)
    if structured.provider != "ocr_only":
        cache.put(key, extraction)
    return extraction


async def run_scan(scan: ScanInput, router: LLMRouter, cache: ExtractionCache) -> ScanResult:
    extraction = await extract(scan, router, cache)
    with stage("engine"):
        output = engine_adapter.evaluate(extraction, scan.profiles)
    return build_scan_result(extraction, output, scan.lang)
