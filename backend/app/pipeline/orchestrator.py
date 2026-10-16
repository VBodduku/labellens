"""The scan flow (master spec §5.1 steps 3-9 and 11).

quality -> cache lookup -> focus + OCR (panels in parallel) -> LLM structuring (Gemini -> backup -> Ollama)
-> alignment -> panel merge -> self-verification -> cache store -> engine -> LLM interpretation of
unresolved terms -> engine again -> per-profile summaries -> ScanResult.
Focus crops each photo to its text, upright and enlarged; OCR, the LLM and verification read that
view and every box is mapped back to the full photo before caching.
When every LLM fails or the LLM budget runs out, the OCR-only reader replaces structuring +
alignment; interpretation and summaries still run on whichever provider is usable (they are short).
Every LLM stage gets what is left of the
45 s budget minus a reserve for the stages after it.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, replace

from backend.app import engine_adapter, errors
from backend.app.cache import CacheExtras, ExtractionCache, cache_key, summary_key
from backend.app.config import get_settings
from backend.app.llm.base import PROSE_PROVIDERS
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.logging_setup import note, stage
from backend.app.pipeline import ocr_only, summarize
from backend.app.pipeline.align import PanelExtraction, TokenIndex, align_panel, panel_image_ids
from backend.app.pipeline.assemble import build_scan_result
from backend.app.pipeline.interpret import interpret
from backend.app.pipeline.focus import FOCUS_VERSION, Focused, read_panel, to_full_frame
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.llm_schema import LLMExtraction
from backend.app.pipeline.merge import MergedLabel, evidence_of, merge_panels
from backend.app.pipeline.quality import add_cropped_edge, assess
from backend.app.pipeline.scan_memory import SCAN_MEMORY, ScanRecord, fingerprint
from backend.app.pipeline.structure import PROMPT_VERSION, Citations, structure
from backend.app.pipeline.verify import scan_unknowns, verify
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
from shared.engine_interface import EngineOutput, TermInterpretation, UnresolvedTerm

SCAN_BUDGET_S = 45.0
STRUCTURE_RESERVE_S = 12.0      # kept back from structuring for verify, interpretation and summaries
VERIFY_RESERVE_S = 8.0          # kept back from verification for interpretation and summaries
INTERPRET_CAP_S, INTERPRET_RESERVE_S = 10.0, 5.0
SUMMARY_CAP_S, SUMMARY_RESERVE_S = 8.0, 1.5
MIN_STAGE_S = 3.0


class Deadline:
    def __init__(self, total_s: float) -> None:
        self._end = time.monotonic() + total_s

    def budget(self, cap_s: float, reserve_s: float) -> float:
        """Seconds a stage may use: at most cap_s, leaving reserve_s for later stages (0 = skip)."""
        available = min(cap_s, self._end - time.monotonic() - reserve_s)
        return available if available >= MIN_STAGE_S else 0.0


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


async def _read_all(images: list[PreparedImage]) -> list[Focused]:
    return list(await asyncio.gather(*(read_panel(image) for image in images)))


def _from_llm(extraction: LLMExtraction, citations: Citations, images: list[PreparedImage],
              tokens: list[OcrToken]) -> list[PanelExtraction]:
    image_ids = [i.image_id for i in images]
    panels = extraction.panels[: len(image_ids)]
    index = TokenIndex(tokens)
    return [align_panel(p, image_id, index, citations.get(image_id, []))
            for p, image_id in zip(panels, panel_image_ids(panels, image_ids))]


def _ocr_only(images: list[PreparedImage], tokens: list[OcrToken]) -> Structured:
    panels = [ocr_only.extract_panel(i.image_id, [t for t in tokens if t.image_id == i.image_id]) for i in images]
    return Structured(merge_panels(panels), "ocr_only", "rapidocr", 0)


async def _structure(scan: ScanInput, tokens: list[OcrToken], router: LLMRouter, budget_s: float) -> Structured:
    try:
        if budget_s <= 0:
            raise TimeoutError
        with stage("llm"):
            structured = await asyncio.wait_for(structure(scan.images, scan.hints, tokens, router), budget_s)
    except (AllProvidersFailedError, TimeoutError) as exc:
        note("llm_failure", type(exc).__name__)
        with stage("ocr_only"):
            return _ocr_only(scan.images, tokens)
    result = structured.result
    with stage("align"):
        panels = _from_llm(result.value, structured.citations, scan.images, tokens)
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


def scan_cache_key(scan: ScanInput) -> str:
    return cache_key(scan.raw, scan.hints, f"{PROMPT_VERSION}+{FOCUS_VERSION}", get_settings().gemini_model)


async def extract(scan: ScanInput, router: LLMRouter, cache: ExtractionCache, deadline: Deadline) -> LabelExtraction:
    started = time.perf_counter()
    key = scan_cache_key(scan)
    cached = cache.get(key)
    if cached is not None:
        note("cache_hit", True)
        return cached.model_copy(update={
            "scan_id": new_scan_id(), "meta": cached.meta.model_copy(update={"cache_hit": True}),
        })

    with stage("quality"):
        qualities = [assess(i) for i in scan.images]
    with stage("ocr"):
        panels = await _read_all(scan.images)
    views = {p.image.image_id: p.view for p in panels}
    note("focus", [f"{p.image.image_id}:turns={p.view.turns},crop={not p.view.identity}" for p in panels])
    qualities = [add_cropped_edge(q, [to_full_frame(t, views) for t in p.tokens]) for q, p in zip(qualities, panels)]
    if not any(p.tokens for p in panels) and all(not q.ok for q in qualities):
        raise errors.bad_image("We could not read any text. Retake the photo closer, in good light.")
    tokens = [t for p in panels for t in p.tokens]
    seen = replace(scan, images=[p.image for p in panels])     # boxes stay on the focused views until verified

    structured = await _structure(seen, tokens, router, deadline.budget(SCAN_BUDGET_S, STRUCTURE_RESERVE_S))
    extraction = _extraction(scan, qualities, tokens, structured, 0)
    verify_budget = deadline.budget(SCAN_BUDGET_S, VERIFY_RESERVE_S)
    if structured.provider != "ocr_only" and verify_budget:
        with stage("verify"):
            extraction = await verify(extraction, seen.images, scan.profiles, router, verify_budget)
    extraction = to_full_frame(extraction, views)
    duration_ms = int((time.perf_counter() - started) * 1000)
    extraction = extraction.model_copy(update={"meta": extraction.meta.model_copy(update={"duration_ms": duration_ms})})

    evidence = evidence_of(structured.label)
    note("provider", structured.provider)
    note("attempts", extraction.meta.attempts)
    note("retries", [f"{r.reason}:{r.outcome}" for r in extraction.meta.retries])
    note("verified_ratio", round(sum(e.status == "verified" for e in evidence) / len(evidence), 3) if evidence else None)
    if structured.provider != "ocr_only":
        cache.put(key, extraction)
    return extraction


def _whole_ingredients_first(output: EngineOutput) -> list[UnresolvedTerm]:
    """Ingredients the KB does not know at all block "not listed"; leftover words of matched ones do not."""
    unknown = {a.ingredient_id for a in output.annotations if a.source == "unresolved"}
    return sorted(output.unresolved_terms, key=lambda t: t.ingredient_id not in unknown)


async def _interpretations(extraction: LabelExtraction, output: EngineOutput, extras: CacheExtras,
                           router: LLMRouter, deadline: Deadline) -> dict[str, TermInterpretation]:
    wanted = {t.term for t in output.unresolved_terms}
    if not wanted:
        return {}
    if wanted <= set(extras.interpreted_terms) or extraction.meta.cache_hit:   # cache hits never wait on an LLM
        return {t: extras.interpretations[t] for t in wanted if t in extras.interpretations}
    budget = deadline.budget(INTERPRET_CAP_S, INTERPRET_RESERVE_S)
    if not budget or not router.can_generate():
        return {}
    with stage("interpret"):
        found = await interpret(_whole_ingredients_first(output), router, budget)
    if found is None:                                    # no model answered: try again next time
        return {}
    extras.interpretations.update(found)
    extras.interpreted_terms = sorted(set(extras.interpreted_terms) | wanted)
    return found


async def _summaries(scan: ScanInput, output: EngineOutput, extras: CacheExtras, router: LLMRouter,
                     deadline: Deadline, cache_hit: bool) -> dict[str, str]:
    keys = {r.profile_id: summary_key(scan.lang, r.profile_id, fingerprint(r)) for r in output.reports}
    cached = {pid: extras.summaries[k] for pid, k in keys.items() if k in extras.summaries}
    if cache_hit or (keys and len(cached) == len(keys)):  # cache hits never wait on an LLM (templates fill gaps)
        return cached
    budget = deadline.budget(SUMMARY_CAP_S, SUMMARY_RESERVE_S)
    if not budget or not router.can_generate(PROSE_PROVIDERS):
        return {}
    with stage("summarize"):
        found = await summarize.summarize(output.reports, scan.profiles, scan.lang, router, budget)
    extras.summaries.update({keys[pid]: text for pid, text in found.items()})
    return found


async def run_scan(scan: ScanInput, router: LLMRouter, cache: ExtractionCache) -> ScanResult:
    deadline = Deadline(SCAN_BUDGET_S)
    extraction = await extract(scan, router, cache, deadline)
    key = scan_cache_key(scan)
    extras = cache.get_extras(key)
    with stage("engine"):
        output = engine_adapter.evaluate(extraction, scan.profiles)

    interpretations = await _interpretations(extraction, output, extras, router, deadline)
    if interpretations:
        with stage("engine"):
            output = engine_adapter.evaluate(extraction, scan.profiles, interpretations)
    summaries = await _summaries(scan, output, extras, router, deadline, extraction.meta.cache_hit)
    if extraction.meta.provider != "ocr_only":
        cache.put_extras(key, extras)

    reports = summarize.apply(output.reports, summaries, scan.lang)
    unknowns = scan_unknowns(extraction, scan.profiles, output.unknowns)
    record = ScanRecord(lang=scan.lang, interpretations=interpretations)
    record.remember_summaries(reports)
    SCAN_MEMORY.put(extraction.scan_id, record)
    return build_scan_result(extraction, output.model_copy(update={"reports": reports, "unknowns": unknowns}), scan.lang)
