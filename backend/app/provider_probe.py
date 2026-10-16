"""Provider checks for /api/health (reachable and allowed to generate), cached for 60 s so polling never hammers providers."""
from __future__ import annotations

import asyncio
import time

import httpx

from backend.app.config import Settings

PROBE_TIMEOUT_S = 3.0
CACHE_TTL_S = 60.0
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
REFUSED_STATUSES = {401, 403}

_cache: tuple[float, dict[str, bool]] | None = None


async def _ok(client: httpx.AsyncClient, url: str, headers: dict[str, str] | None = None) -> bool:
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


async def _generation_refused(client: httpx.AsyncClient, settings: Settings, headers: dict[str, str]) -> bool:
    """A key whose project Google has blocked still lists models (and counts tokens) but gets 401/403 on
    every generation. One 1-token generation tells them apart; rate limits and overload are not refusals."""
    try:
        response = await client.post(
            f"{GEMINI_MODELS_URL}/{settings.gemini_model}:generateContent", headers=headers,
            json={"contents": [{"parts": [{"text": "OK"}]}], "generationConfig": {"maxOutputTokens": 1}},
        )
    except httpx.HTTPError:
        return False
    return response.status_code in REFUSED_STATUSES


async def _gemini(client: httpx.AsyncClient, settings: Settings) -> bool:
    if not settings.gemini_api_key:
        return False
    headers = {"x-goog-api-key": settings.gemini_api_key}
    return await _ok(client, GEMINI_MODELS_URL, headers) and not await _generation_refused(client, settings, headers)


async def _ollama(client: httpx.AsyncClient, settings: Settings) -> bool:
    return await _ok(client, f"{settings.ollama_base_url}/api/tags")


async def probe_providers(settings: Settings) -> dict[str, bool]:
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < CACHE_TTL_S:
        return dict(_cache[1])
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
        gemini, ollama = await asyncio.gather(_gemini(client, settings), _ollama(client, settings))
    status = {"gemini": gemini, "ollama": ollama}
    _cache = (now, status)
    return dict(status)


def reset_cache() -> None:
    global _cache
    _cache = None
