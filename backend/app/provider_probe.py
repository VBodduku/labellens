"""Reachability checks for /api/health, cached for 60 s so health polling never hammers providers."""
from __future__ import annotations

import asyncio
import time

import httpx

from backend.app.config import Settings

PROBE_TIMEOUT_S = 3.0
CACHE_TTL_S = 60.0
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_cache: tuple[float, dict[str, bool]] | None = None


async def _ok(client: httpx.AsyncClient, url: str, headers: dict[str, str] | None = None) -> bool:
    try:
        response = await client.get(url, headers=headers)
    except httpx.HTTPError:
        return False
    return response.status_code == 200


async def _gemini(client: httpx.AsyncClient, settings: Settings) -> bool:
    if not settings.gemini_api_key:
        return False
    return await _ok(client, GEMINI_MODELS_URL, {"x-goog-api-key": settings.gemini_api_key})


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
