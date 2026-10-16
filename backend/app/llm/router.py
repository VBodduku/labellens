"""Fallback chain over LLM clients: timeouts, 429 cooldowns, schema validation with one repair attempt."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.config import get_settings
from backend.app.llm.base import LLMClient, LLMError, LLMImage, ProviderName, RateLimitedError, ToolChatClient
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.ollama import OllamaClient
from backend.app.llm.schema_utils import inline_schema

logger = logging.getLogger("labellens.llm")

M = TypeVar("M", bound=BaseModel)

TIMEOUT_COOLDOWN_S = 300       # a provider too slow for image calls is skipped for them a while (local Ollama)
REPAIR_INSTRUCTION = (
    "\n\nYour previous answer did not match the required JSON schema. Validation errors:\n{errors}\n"
    "Return the corrected JSON only."
)


@dataclass
class ClientState:
    client: LLMClient
    cooldown_until: float = 0.0         # rate limited: skipped for every call
    slow_until: float = 0.0             # timed out on an image call: skipped for image calls only
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

    def tool_clients(self) -> list[ToolChatClient]:
        """Clients that can call tools (Gemini) and are not cooling down, in fallback order."""
        now = self._clock()
        return [s.client for s in self._states  # type: ignore[misc]
                if s.cooldown_until <= now and hasattr(s.client, "chat_with_tools")]

    def tool_client(self) -> ToolChatClient | None:
        clients = self.tool_clients()
        return clients[0] if clients else None

    def report_rate_limit(self, client_label: str, retry_after_s: int) -> None:
        """Let callers that talk to a client directly (the agent) share the cooldown bookkeeping."""
        for state in self._states:
            if state.client.label == client_label:
                state.cooldown_until = self._clock() + retry_after_s

    def can_generate(self, providers: Collection[ProviderName] | None = None) -> bool:
        return any(state.cooldown_until <= self._clock() and (providers is None or state.client.name in providers)
                   for state in self._states)

    async def generate(
        self, prompt_for: Callable[[ProviderName], str], images: list[LLMImage], schema_model: type[M],
        timeout_s: float | None = None, providers: Collection[ProviderName] | None = None,
    ) -> LLMResult[M]:
        """`providers` restricts the chain (e.g. user-facing prose only from Gemini)."""
        schemas = {flag: inline_schema(schema_model, require_all=flag) for flag in (True, False)}
        timeout = min(self._timeout_s, timeout_s) if timeout_s is not None else self._timeout_s
        attempts = 0
        retry_after: list[int] = []
        for state in self._states:
            if providers is not None and state.client.name not in providers:
                continue
            if state.cooldown_until > self._clock():
                retry_after.append(int(state.cooldown_until - self._clock()) + 1)
                continue
            if images and state.slow_until > self._clock():
                continue
            prompt = prompt_for(state.client.name)
            schema = schemas[getattr(state.client, "require_all_fields", True)]
            for repair in (False, True):
                attempts += 1
                try:
                    text = await asyncio.wait_for(state.client.generate_json(prompt, images, schema, timeout), timeout)
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
                    if images and timeout >= self._timeout_s:   # too slow for photos, not a short caller budget
                        state.slow_until = self._clock() + TIMEOUT_COOLDOWN_S
                    self._fail(state, f"timed out after {timeout:g}s")
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
    return LLMRouter(gemini_clients() + [OllamaClient(get_settings().ollama_base_url, get_settings().ollama_model)],
                     get_settings().llm_timeout_s)


def gemini_clients() -> list[LLMClient]:
    """Each key with the main model, then the fallback model: Google's overload (503) and free quota
    (429) apply per model, so a second model on the same key often still answers."""
    settings = get_settings()
    models = list(dict.fromkeys(m for m in (settings.gemini_model, settings.gemini_fallback_model) if m))
    keys = [("primary", settings.gemini_api_key), ("backup", settings.gemini_api_key_backup)]
    return [GeminiClient(key, model, f"gemini:{name}:{model}") for name, key in keys if key for model in models]
