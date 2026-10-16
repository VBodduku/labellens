"""Offline LLM fakes and small builders shared by the tests."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from backend.app.llm.base import LLMImage, ProviderName
from backend.app.llm.router import LLMRouter
from shared.contract import Box, OcrToken

DATA_DIR = Path(__file__).parent / "data"


def recorded(name: str) -> str:
    return (DATA_DIR / name).read_text(encoding="utf-8")


class FakeLLM:
    """Returns (or raises) the queued responses in order; the last one repeats."""

    def __init__(self, responses: Sequence[str | BaseException], name: ProviderName = "gemini",
                 label: str | None = None, model: str = "fake-model", delay_s: float = 0.0) -> None:
        self.name = name
        self.label = label or name
        self.model = model
        self.responses = list(responses)
        self.delay_s = delay_s
        self.prompts: list[str] = []
        self.images: list[list[LLMImage]] = []
        self.schemas: list[dict[str, Any]] = []

    async def generate_json(self, prompt: str, images: list[LLMImage], schema: dict[str, Any], timeout_s: float) -> str:
        self.prompts.append(prompt)
        self.images.append(images)
        self.schemas.append(schema)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        response = self.responses[min(len(self.prompts) - 1, len(self.responses) - 1)]
        if isinstance(response, BaseException):
            raise response
        return response


def router_with(*clients: FakeLLM, timeout_s: float = 5.0) -> LLMRouter:
    return LLMRouter(list(clients), timeout_s)


def token(n: int, text: str, x: float, y: float, w: float = 0.08, h: float = 0.02,
          image_id: str = "img_0", confidence: float = 0.95) -> OcrToken:
    return OcrToken(token_id=f"{image_id}:t{n}", image_id=image_id, text=text,
                    box=Box(x=x, y=y, w=w, h=h), confidence=confidence)


def line_tokens(words: Sequence[str], y: float, start: int = 0, x0: float = 0.05,
                image_id: str = "img_0") -> list[OcrToken]:
    """Tokens laid out left to right on one printed line."""
    tokens: list[OcrToken] = []
    x = x0
    for n, word in enumerate(words):
        width = 0.012 * len(word)
        tokens.append(token(start + n, word, x, y, w=width, image_id=image_id))
        x += width + 0.01
    return tokens
