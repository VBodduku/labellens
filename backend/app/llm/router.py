"""Fallback chain over LLM clients: timeouts, 429 cooldowns, schema validation with one repair attempt."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from backend.app.config import get_settings
from backend.app.llm.base import (
    AccessDeniedError,
    LLMClient,
    LLMError,
    LLMImage,
    ModelOverloadedError,
    ProviderName,
    RateLimitedError,
    ToolChatClient,
)
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.ollama import OllamaClient
from backend.app.llm.schema_utils import inline_schema

logger = logging.getLogger("labellens.llm")

M = TypeVar("M", bound=BaseModel)

TIMEOUT_COOLDOWN_S = 300       # a provider too slow for image calls is skipped for them a while (local Ollama)
MIN_ATTEMPT_S = 2.0            # less left of a caller's budget than this: stop trying further models
HEDGE_SHARE = 0.5              # a model silent for this share of the time left gets the next model started beside it
REPAIR_INSTRUCTION = (
    "\n\nYour previous answer did not match the required JSON schema. Validation errors:\n{errors}\n"
    "Return the corrected JSON only."
)


@dataclass
class ClientState:
    client: LLMClient
    cooldown_until: float = 0.0         # rate limited, overloaded or refused: skipped for every call
    rate_limited: bool = False          # the cooldown is a quota limit (worth telling the user to retry later)
    slow_until: float = 0.0             # timed out on an image call: skipped for image calls only
    last_ok: float | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class LLMResult(Generic[M]):
    value: M
    provider: ProviderName
    model: str
    attempts: int


@dataclass
class _Run:
    """Shared bookkeeping of one generate() call across the models it tries (possibly two at once)."""
    schemas: dict[bool, dict]
    timeout: float
    deadline: float | None
    check: Callable[[Any], str | None] | None = None
    attempts: int = 0
    retry_after: list[int] = field(default_factory=list)


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
                state.rate_limited = True

    def report_access_denied(self, client_label: str, retry_after_s: int) -> None:
        """A refused key fails for every model: skip all clients that share it ("gemini:primary:*")."""
        key = _key_of(client_label)
        for state in self._states:
            if _key_of(state.client.label) == key:
                state.cooldown_until = self._clock() + retry_after_s
                state.rate_limited = False
                state.last_error = f"access denied, key skipped for {retry_after_s}s"

    def can_generate(self, providers: Collection[ProviderName] | None = None) -> bool:
        return any(state.cooldown_until <= self._clock() and (providers is None or state.client.name in providers)
                   for state in self._states)

    async def generate(
        self, prompt_for: Callable[[ProviderName], str], images: list[LLMImage], schema_model: type[M],
        timeout_s: float | None = None, providers: Collection[ProviderName] | None = None,
        check: Callable[[M], str | None] | None = None,
    ) -> LLMResult[M]:
        """`providers` restricts the chain (e.g. user-facing prose only from Gemini). `timeout_s` is the
        caller's budget for the whole chain; without it each attempt gets LLM_TIMEOUT_S. `check` rejects a
        schema-valid answer that is still unusable (it returns the reason), like invalid JSON: one repair, then
        the next model.

        Models are tried in order. With a budget, a model that has used HEDGE_SHARE of the time left without
        answering is not waited out alone: the next model starts alongside it and the first valid answer wins.
        An overloaded model can take ~30 s just to return its 503, which used to leave the fallbacks no time.
        A model that answers in time costs no extra call."""
        run = _Run(
            schemas={flag: inline_schema(schema_model, require_all=flag) for flag in (True, False)},
            timeout=min(self._timeout_s, timeout_s) if timeout_s is not None else self._timeout_s,
            deadline=self._clock() + timeout_s if timeout_s is not None else None,
            check=check,
        )
        waiting = [s for s in self._states if providers is None or s.client.name in providers]
        running: dict[asyncio.Task[LLMResult[M] | None], ClientState] = {}
        hedge_at: float | None = None

        def start_next() -> float | None:
            """Start the next usable model; returns when to hedge it (None: no budget, or nothing left)."""
            while waiting:
                state = waiting.pop(0)
                if self._usable(state, images, run.retry_after):
                    task = asyncio.create_task(self._attempt(state, prompt_for, images, schema_model, run))
                    running[task] = state
                    if run.deadline is None or not waiting:
                        return None
                    return self._clock() + HEDGE_SHARE * (run.deadline - self._clock())
            return None

        hedge_at = start_next()
        try:
            while running:
                wait_s = max(0.0, hedge_at - self._clock()) if hedge_at is not None else None
                done, _ = await asyncio.wait(running, timeout=wait_s, return_when=asyncio.FIRST_COMPLETED)
                if not done:                                    # the current model is slow: hedge with the next
                    hedge_at = start_next()
                    continue
                for task in done:
                    running.pop(task)
                    result = task.result()
                    if result is not None:
                        return result
                    hedge_at = start_next()                     # a failed model's turn passes on straight away
        finally:
            for task in running:
                task.cancel()
        raise AllProvidersFailedError(rate_limited=bool(run.retry_after),
                                      retry_after_s=min(run.retry_after, default=None))

    def _usable(self, state: ClientState, images: list[LLMImage], retry_after: list[int]) -> bool:
        """Checked when a model's turn comes, so a key refused or rate limited meanwhile is skipped."""
        if state.cooldown_until > self._clock():
            if state.rate_limited:
                retry_after.append(int(state.cooldown_until - self._clock()) + 1)
            return False
        return not (images and state.slow_until > self._clock())

    async def _attempt(
        self, state: ClientState, prompt_for: Callable[[ProviderName], str], images: list[LLMImage],
        schema_model: type[M], run: "_Run",
    ) -> LLMResult[M] | None:
        """One model: a call plus one repair attempt on invalid JSON or an unusable answer. None when it failed."""
        prompt = prompt_for(state.client.name)
        schema = run.schemas[getattr(state.client, "require_all_fields", True)]
        for repair in (False, True):
            limit = run.timeout if run.deadline is None else min(run.timeout, run.deadline - self._clock())
            if run.deadline is not None and limit < MIN_ATTEMPT_S:
                return None
            run.attempts += 1
            try:
                text = await asyncio.wait_for(state.client.generate_json(prompt, images, schema, limit), limit)
                value = schema_model.model_validate_json(text)
                problem = run.check(value) if run.check else None
            except ValidationError as exc:
                self._fail(state, f"invalid output: {exc.error_count()} errors")
                if repair:
                    return None
                prompt = prompt + REPAIR_INSTRUCTION.format(errors=_short_errors(exc))
                continue
            except RateLimitedError as exc:
                state.cooldown_until = self._clock() + exc.retry_after_s
                state.rate_limited = True
                run.retry_after.append(exc.retry_after_s)
                self._fail(state, f"rate limited for {exc.retry_after_s}s")
                return None
            except AccessDeniedError as exc:
                self.report_access_denied(state.client.label, exc.retry_after_s)
                self._fail(state, f"access denied, key skipped for {exc.retry_after_s}s")
                return None
            except ModelOverloadedError as exc:
                state.cooldown_until = self._clock() + exc.retry_after_s
                state.rate_limited = False
                self._fail(state, f"overloaded, skipped for {exc.retry_after_s}s")
                return None
            except TimeoutError:
                if images and limit >= self._timeout_s:     # too slow for photos, not a short caller budget
                    state.slow_until = self._clock() + TIMEOUT_COOLDOWN_S
                self._fail(state, f"timed out after {limit:g}s")
                return None
            except LLMError as exc:
                self._fail(state, str(exc) or type(exc).__name__)
                return None
            if problem:
                self._fail(state, f"unusable answer: {problem}")
                if repair:
                    return None
                prompt = prompt + REPAIR_INSTRUCTION.format(errors=f"- {problem}")
                continue
            state.last_ok, state.last_error = self._clock(), None
            return LLMResult(value=value, provider=state.client.name, model=state.client.model, attempts=run.attempts)
        return None

    def _fail(self, state: ClientState, reason: str) -> None:
        state.last_error = reason
        logger.warning("llm call failed", extra={"fields": {"client": state.client.label, "reason": reason}})


def _key_of(label: str) -> str:
    """The API key part of a client label: "gemini:primary:gemini-flash-latest" -> "gemini:primary"."""
    return label.rsplit(":", 1)[0] if label.count(":") >= 2 else label


def _short_errors(exc: ValidationError) -> str:
    return "\n".join(
        f"- {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:10]
    )


@lru_cache(maxsize=1)
def get_router() -> LLMRouter:
    return LLMRouter(gemini_clients() + [OllamaClient(get_settings().ollama_base_url, get_settings().ollama_model)],
                     get_settings().llm_timeout_s)


def gemini_clients() -> list[LLMClient]:
    """Each key with the main model, then the fallback models in order: Google's overload (503) and free
    quota (429) apply per model, so another model on the same key often still answers."""
    settings = get_settings()
    models = list(dict.fromkeys(m for m in (settings.gemini_model, *settings.gemini_fallback_models) if m))
    keys = [("primary", settings.gemini_api_key), ("backup", settings.gemini_api_key_backup)]
    return [GeminiClient(key, model, f"gemini:{name}:{model}") for name, key in keys if key for model in models]
