"""Gemini client (google-genai): schema-constrained JSON, temperature 0, no SDK-side retries."""
from __future__ import annotations

import re
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from backend.app.llm.base import (
    InvalidOutputError,
    LLMImage,
    ProviderName,
    ProviderUnavailableError,
    RateLimitedError,
)

DEFAULT_RETRY_AFTER_S = 60
_RETRY_DELAY = re.compile(r"^(\d+(?:\.\d+)?)s$")


def retry_after_from(details: Any) -> int:
    """Read google.rpc.RetryInfo.retryDelay ("17s") from a 429 error body."""
    error = details.get("error", details) if isinstance(details, dict) else {}
    for item in error.get("details", []) if isinstance(error, dict) else []:
        delay = item.get("retryDelay") if isinstance(item, dict) else None
        match = _RETRY_DELAY.match(delay) if isinstance(delay, str) else None
        if match:
            return max(1, round(float(match.group(1))))
    return DEFAULT_RETRY_AFTER_S


class GeminiClient:
    name: ProviderName = "gemini"

    def __init__(self, api_key: str, model: str, label: str = "gemini") -> None:
        self.label = label
        self.model = model
        self._api_key = api_key

    def _client(self, timeout_s: float) -> genai.Client:
        return genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_s * 1000),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    async def generate_json(
        self, prompt: str, images: list[LLMImage], schema: dict[str, Any], timeout_s: float,
    ) -> str:
        contents: list[Any] = [types.Part.from_bytes(data=i.data, mime_type=i.mime_type) for i in images]
        contents.append(prompt)
        config = types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        try:
            response = await self._client(timeout_s).aio.models.generate_content(
                model=self.model, contents=contents, config=config,
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise RateLimitedError(retry_after_from(exc.details)) from exc
            raise ProviderUnavailableError(f"gemini HTTP {exc.code} {exc.status or ''}".strip()) from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise ProviderUnavailableError(f"gemini network error: {type(exc).__name__}") from exc
        text = response.text
        if not text:
            raise InvalidOutputError("gemini returned no text")
        return text
