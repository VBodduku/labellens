"""Offline LLM fakes and small builders shared by the tests."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from backend.app.llm.base import InvalidOutputError, LLMImage, ProviderName, ProviderUnavailableError
from backend.app.llm.router import LLMRouter
from shared.contract import Box, OcrToken

DATA_DIR = Path(__file__).parent / "data"


def recorded(name: str) -> str:
    return (DATA_DIR / name).read_text(encoding="utf-8")


# Phrases that identify each prompt kind (see backend/app/llm/prompts/).
STRUCTURE = "TRANSCRIBE the label"
REREAD = "# Focused re-read"
INTERPRET = "rules engine could not find"
SUMMARIZE = "one-sentence summaries"

Response = str | BaseException


class FakeLLM:
    """Scripted model. `routes` maps a phrase in the prompt to its responses; other prompts use
    `responses`. Each list is consumed in order and its last entry repeats."""

    def __init__(self, responses: Sequence[Response] = (), name: ProviderName = "gemini",
                 label: str | None = None, model: str = "fake-model", delay_s: float = 0.0,
                 routes: dict[str, Sequence[Response]] | None = None) -> None:
        self.name = name
        self.label = label or name
        self.model = model
        self.responses = list(responses)
        self.routes = {k: list(v) for k, v in (routes or {}).items()}
        self.delay_s = delay_s
        self.prompts: list[str] = []
        self.images: list[list[LLMImage]] = []
        self.schemas: list[dict[str, Any]] = []

    @staticmethod
    def _matches(phrase: str, prompt: str) -> bool:
        # A re-read prompt embeds the structuring rules; it only counts as a re-read.
        return phrase in prompt and not (phrase == STRUCTURE and REREAD in prompt)

    def calls(self, phrase: str) -> list[str]:
        return [p for p in self.prompts if self._matches(phrase, p)]

    def _next(self, prompt: str) -> Response:
        for phrase in sorted(self.routes, key=len, reverse=True):
            if self._matches(phrase, prompt):
                queue, used = self.routes[phrase], len(self.calls(phrase)) - 1
                return queue[min(used, len(queue) - 1)]
        if not self.responses:
            return InvalidOutputError(f"FakeLLM has no response for this prompt: {prompt[:60]!r}")
        unrouted = [p for p in self.prompts if not any(ph in p for ph in self.routes)]
        return self.responses[min(len(unrouted) - 1, len(self.responses) - 1)]

    async def generate_json(self, prompt: str, images: list[LLMImage], schema: dict[str, Any], timeout_s: float) -> str:
        self.prompts.append(prompt)
        self.images.append(images)
        self.schemas.append(schema)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        response = self._next(prompt)
        if isinstance(response, BaseException):
            raise response
        return response


def scan_llm(structure: Response, name: ProviderName = "ollama", model: str = "gemma3:4b",
             **routes: Sequence[Response]) -> FakeLLM:
    """A scan model: answers structuring with `structure`; re-read/interpret/summarize are unavailable
    unless given (reread=…, interpret=…, summarize=…)."""
    down: list[Response] = [ProviderUnavailableError("not scripted")]
    return FakeLLM(name=name, model=model, routes={
        STRUCTURE: [structure],
        REREAD: routes.get("reread", down),
        INTERPRET: routes.get("interpret", down),
        SUMMARIZE: routes.get("summarize", down),
    })


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
