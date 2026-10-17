"""POST /api/scan and POST /api/recheck."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import TypeAdapter, ValidationError

from backend.app import engine_adapter, errors
from backend.app.cache import ExtractionCache, get_cache
from backend.app.config import get_settings
from backend.app.llm.base import PROSE_PROVIDERS
from backend.app.llm.router import LLMRouter, get_router
from backend.app.logging_setup import stage
from backend.app.pipeline import summarize
from backend.app.pipeline.assemble import build_scan_result
from backend.app.pipeline.images import BadImageError, PreparedImage, decode_upload, image_id
from backend.app.pipeline.orchestrator import ScanInput, run_scan
from backend.app.pipeline.scan_memory import SCAN_MEMORY
from backend.app.pipeline.verify import scan_unknowns
from shared.contract import Lang, PanelHint, Profile, RecheckRequest, ScanResult

router = APIRouter(prefix="/api")

_PROFILES = TypeAdapter(list[Profile])
_PANEL_HINTS = TypeAdapter(list[PanelHint])
_CHUNK = 1024 * 1024


def parse_profiles(raw: str) -> list[Profile]:
    try:
        return _PROFILES.validate_json(raw)
    except ValidationError as exc:
        raise errors.validation(f"profiles must be a JSON list of profiles ({exc.error_count()} problems).") from exc


def parse_panel_hints(raw: str | None, image_count: int) -> list[PanelHint]:
    if raw is None or not raw.strip():
        return []
    try:
        hints = _PANEL_HINTS.validate_json(raw)
    except ValidationError as exc:
        raise errors.validation("panel_hints must be a JSON list of front/back/side/unknown.") from exc
    if len(hints) > image_count:
        raise errors.validation("panel_hints has more entries than images.")
    return hints


async def read_limited(upload: UploadFile, limit: int) -> bytes:
    data = bytearray()
    while chunk := await upload.read(_CHUNK):
        data.extend(chunk)
        if len(data) > limit:
            raise errors.image_too_large(get_settings().max_image_mb)
    return bytes(data)


async def read_images(uploads: list[UploadFile]) -> tuple[list[bytes], list[PreparedImage]]:
    settings = get_settings()
    if not uploads:
        raise errors.validation("Attach at least one photo of the label.")
    if len(uploads) > settings.max_images:
        raise errors.too_many_images(settings.max_images)
    raw: list[bytes] = []
    prepared: list[PreparedImage] = []
    for index, upload in enumerate(uploads):
        data = await read_limited(upload, settings.max_image_bytes)
        try:
            prepared.append(await run_in_threadpool(decode_upload, data, image_id(index)))
        except BadImageError as exc:
            raise errors.bad_image(f"Photo {index + 1}: {exc}") from exc
        raw.append(data)
    return raw, prepared


@router.post("/scan", response_model=ScanResult)
async def scan(
    profiles: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()] = [],  # noqa: B006 - FastAPI reads the default, never mutates it
    lang: Annotated[Lang, Form()] = "en",
    panel_hints: Annotated[str | None, Form()] = None,
    router: LLMRouter = Depends(get_router),
    cache: ExtractionCache = Depends(get_cache),
) -> ScanResult:
    parsed_profiles = parse_profiles(profiles)
    with stage("decode"):
        raw, prepared = await read_images(images)
    hints = parse_panel_hints(panel_hints, len(prepared))
    scan_input = ScanInput(images=prepared, raw=raw, hints=hints, profiles=parsed_profiles, lang=lang)
    try:
        return await asyncio.wait_for(run_scan(scan_input, router, cache), get_settings().scan_budget_s)
    except TimeoutError as exc:
        raise errors.ApiError(503, "LLM_UNAVAILABLE", "Reading the label took too long. Please try again.") from exc


RECHECK_SUMMARY_BUDGET_S = 8.0


@router.post("/recheck", response_model=ScanResult)
async def recheck(body: RecheckRequest, router: LLMRouter = Depends(get_router)) -> ScanResult:
    """Engine only. Summaries: regenerated when the language changed, reused only for unchanged verdicts."""
    record = SCAN_MEMORY.get(body.extraction.scan_id)
    with stage("engine"):
        output = engine_adapter.evaluate(body.extraction, body.profiles, record.interpretations if record else None)
    summaries: dict[str, str] = {}
    if record is not None and body.lang != record.lang and router.can_generate(PROSE_PROVIDERS):
        with stage("summarize"):
            summaries = await summarize.summarize(output.reports, body.profiles, body.lang, router,
                                                  RECHECK_SUMMARY_BUDGET_S)
    elif record is not None:
        summaries = record.reusable_summaries(output.reports)
    reports = summarize.apply(output.reports, summaries, body.lang)
    if record is not None and summaries:
        record.lang = body.lang
        record.remember_summaries(reports)
    unknowns = scan_unknowns(body.extraction, body.profiles, output.unknowns)
    return build_scan_result(body.extraction, output.model_copy(update={"reports": reports, "unknowns": unknowns}),
                             body.lang)
