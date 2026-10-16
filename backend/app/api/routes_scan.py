"""POST /api/scan and POST /api/recheck."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import TypeAdapter, ValidationError

from backend.app import engine_adapter, errors, fixtures
from backend.app.config import get_settings
from backend.app.logging_setup import stage
from backend.app.pipeline.assemble import build_scan_result
from backend.app.pipeline.images import BadImageError, PreparedImage, decode_upload, image_id
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


async def read_images(uploads: list[UploadFile]) -> list[PreparedImage]:
    settings = get_settings()
    if not uploads:
        raise errors.validation("Attach at least one photo of the label.")
    if len(uploads) > settings.max_images:
        raise errors.too_many_images(settings.max_images)
    prepared: list[PreparedImage] = []
    for index, upload in enumerate(uploads):
        data = await read_limited(upload, settings.max_image_bytes)
        try:
            prepared.append(await run_in_threadpool(decode_upload, data, image_id(index)))
        except BadImageError as exc:
            raise errors.bad_image(f"Photo {index + 1}: {exc}") from exc
    return prepared


@router.post("/scan", response_model=ScanResult)
async def scan(
    profiles: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()] = [],  # noqa: B006 - FastAPI reads the default, never mutates it
    lang: Annotated[Lang, Form()] = "en",
    panel_hints: Annotated[str | None, Form()] = None,
) -> ScanResult:
    parse_profiles(profiles)
    with stage("decode"):
        prepared = await read_images(images)
    parse_panel_hints(panel_hints, len(prepared))
    result = fixtures.scan_result()
    result.lang = lang
    return result


@router.post("/recheck", response_model=ScanResult)
def recheck(body: RecheckRequest) -> ScanResult:
    with stage("engine"):
        output = engine_adapter.evaluate(body.extraction, body.profiles)
    return build_scan_result(body.extraction, output, body.lang)
