"""Fallback chain over LLM clients: timeouts, 429 cooldowns, schema validation with one repair attempt."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.config import get_settings
from backend.app.llm.base import LLMClient, LLMError, LLMImage, ProviderName, RateLimitedError
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.ollama import OllamaClient
from backend.app.llm.schema_utils import inline_schema

logger = logging.getLogger("labellens.llm")

M = TypeVar("M", bound=BaseModel)

TIMEOUT_COOLDOWN_S = 300       # a provider too slow for the scan budget is skipped for a while (local Ollama)
REPAIR_INSTRUCTION = (
    "\n\nYour previous answer did not match the required JSON schema. Validation errors:\n{errors}\n"
    "Return the corrected JSON only."
)


@dataclass
class ClientState:
    client: LLMClient
    cooldown_until: float = 0.0
    last_ok: float | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class LLMResult(Generic[M]):
    value: M
    provider: ProviderName
    model: str
    attempts: int


class AllProvidersFailedError(Exception):
    def __init__(self, rate_limited: bool, retry_after_s: int | None) -> None:
        super().__init__("every LLM provider failed")
        self.rate_limited = rate_limited
        self.retry_after_s = retry_after_s


class LLMRouter:
    def __init__(self, clients: Sequence[LLMClient], timeout_s: float, clock: Callable[[], float] = time.monotonic):
        self._states = [ClientState(c) for c in clients]
        self._timeout_s = timeout_s
        self._clock = clock

    def provider_status(self) -> dict[str, bool]:
        """Per provider: is at least one of its clients configured and not cooling down?"""
        now = self._clock()
        status: dict[str, bool] = {"gemini": False, "ollama": False}
        for state in self._states:
            status[state.client.name] = status[state.client.name] or state.cooldown_until <= now
        return status

    async def generate(
        self, prompt_for: Callable[[ProviderName], str], images: list[LLMImage], schema_model: type[M],
    ) -> LLMResult[M]:
        schema = inline_schema(schema_model)
        attempts = 0
        retry_after: list[int] = []
        for state in self._states:
            if state.cooldown_until > self._clock():
                retry_after.append(int(state.cooldown_until - self._clock()) + 1)
                continue
            prompt = prompt_for(state.client.name)
            for repair in (False, True):
                attempts += 1
                try:
                    text = await asyncio.wait_for(
                        state.client.generate_json(prompt, images, schema, self._timeout_s), self._timeout_s,
                    )
                    value = schema_model.model_validate_json(text)
                except ValidationError as exc:
                    self._fail(state, f"invalid output: {exc.error_count()} errors")
                    if repair:
                        break
                    prompt = prompt + REPAIR_INSTRUCTION.format(errors=_short_errors(exc))
                    continue
                except RateLimitedError as exc:
                    state.cooldown_until = self._clock() + exc.retry_after_s
                    retry_after.append(exc.retry_after_s)
                    self._fail(state, f"rate limited for {exc.retry_after_s}s")
                    break
                except TimeoutError:
                    state.cooldown_until = self._clock() + TIMEOUT_COOLDOWN_S
                    self._fail(state, f"timed out; skipped for {TIMEOUT_COOLDOWN_S}s")
                    break
                except LLMError as exc:
                    self._fail(state, str(exc) or type(exc).__name__)
                    break
                state.last_ok, state.last_error = self._clock(), None
                return LLMResult(value=value, provider=state.client.name, model=state.client.model, attempts=attempts)
        raise AllProvidersFailedError(rate_limited=bool(retry_after), retry_after_s=min(retry_after, default=None))

    def _fail(self, state: ClientState, reason: str) -> None:
        state.last_error = reason
        logger.warning("llm call failed", extra={"fields": {"client": state.client.label, "reason": reason}})


def _short_errors(exc: ValidationError) -> str:
    return "\n".join(
        f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:10]
    )


@lru_cache(maxsize=1)
def get_router() -> LLMRouter:
    settings = get_settings()
    clients: list[LLMClient] = []
    if settings.gemini_api_key:
        clients.append(GeminiClient(settings.gemini_api_key, settings.gemini_model, "gemini:primary"))
    if settings.gemini_api_key_backup:
        clients.append(GeminiClient(settings.gemini_api_key_backup, settings.gemini_model, "gemini:backup"))
    clients.append(OllamaClient(settings.ollama_base_url, settings.ollama_model))
    return LLMRouter(clients, settings.llm_timeout_s)
