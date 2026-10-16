"""Ollama client: POST /api/chat with base64 images and a JSON-schema `format` (structured outputs)."""
from __future__ import annotations

import base64
from typing import Any

import httpx

from backend.app.llm.base import InvalidOutputError, LLMImage, ProviderName, ProviderUnavailableError

NUM_CTX = 8192                  # the default context window truncates the prompt (OCR list comes last)


class OllamaClient:
    name: ProviderName = "ollama"

    def __init__(self, base_url: str, model: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.label = "ollama"
        self.model = model
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def generate_json(
        self, prompt: str, images: list[LLMImage], schema: dict[str, Any], timeout_s: float,
    ) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": NUM_CTX},
            "messages": [{
                "role": "user",
                "content": prompt,
                "images": [base64.b64encode(i.data).decode("ascii") for i in images],
            }],
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s, transport=self._transport) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"ollama network error: {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise ProviderUnavailableError(f"ollama HTTP {response.status_code}")
        try:
            content = response.json()["message"]["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidOutputError("ollama response had no message content") from exc
        if not isinstance(content, str) or not content.strip():
            raise InvalidOutputError("ollama returned empty content")
        return content
