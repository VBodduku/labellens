"""Gemini client (google-genai): schema-constrained JSON, temperature 0, no SDK-side retries."""
from __future__ import annotations

import re
from typing import Any

from google import genai
from google.genai import errors, types

from backend.app.llm.base import (
    ChatMessage,
    InvalidOutputError,
    LLMImage,
    ProviderName,
    ProviderUnavailableError,
    RateLimitedError,
    ToolCall,
    ToolSpec,
)

DEFAULT_RETRY_AFTER_S = 60
# Google rejects request deadlines under 10 s (400 "Minimum allowed deadline is 10s") and expires
# ones right at 10 s; our own budget is enforced client-side by the router's wait_for instead.
MIN_SERVER_DEADLINE_S = 15.0
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
    require_all_fields = False          # optional fields stay optional: shorter answers, lower latency

    def __init__(self, api_key: str, model: str, label: str = "gemini") -> None:
        self.label = label
        self.model = model
        self._api_key = api_key
        self._sdk: genai.Client | None = None

    def _client(self) -> genai.Client:
        """One SDK client for the lifetime of this object. A temporary client can be garbage-collected
        mid-request, which closes its HTTP connection ("client has been closed")."""
        if self._sdk is None:
            self._sdk = genai.Client(api_key=self._api_key, http_options=_http_options(None))
        return self._sdk

    async def _generate(self, contents: Any, config: types.GenerateContentConfig, timeout_s: float) -> Any:
        config = config.model_copy(update={"http_options": _http_options(timeout_s)})
        try:
            return await self._client().aio.models.generate_content(
                model=self.model, contents=contents, config=config,
            )
        except errors.APIError as exc:
            if exc.code == 429:
                raise RateLimitedError(retry_after_from(exc.details)) from exc
            raise ProviderUnavailableError(f"gemini HTTP {exc.code} {exc.status or ''}".strip()) from exc
        except Exception as exc:  # SDK/network failures of any kind must fall back, never 500
            raise ProviderUnavailableError(f"gemini client error: {type(exc).__name__}") from exc

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
        response = await self._generate(contents, config, timeout_s)
        text = response.text
        if not text:
            raise InvalidOutputError("gemini returned no text")
        return text

    async def chat_with_tools(
        self, messages: list[ChatMessage], tools: list[ToolSpec], system: str, timeout_s: float,
    ) -> ChatMessage:
        config = types.GenerateContentConfig(
            temperature=0,
            system_instruction=system,
            tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name=t.name, description=t.description, parameters_json_schema=t.parameters)
                for t in tools
            ])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        response = await self._generate([to_content(m) for m in messages], config, timeout_s)
        candidates = response.candidates or []
        raw = candidates[0].content if candidates else None
        calls = [ToolCall(name=c.name or "", args=dict(c.args or {})) for c in response.function_calls or []]
        text = None if calls else response.text
        if not calls and not text:
            raise InvalidOutputError("gemini returned neither tool calls nor text")
        return ChatMessage(role="model", text=text, calls=calls, raw=raw)


def _http_options(timeout_s: float | None) -> types.HttpOptions:
    """No SDK-side retries (the router owns fallback); per-request timeout in milliseconds."""
    return types.HttpOptions(
        timeout=int(max(timeout_s, MIN_SERVER_DEADLINE_S) * 1000) if timeout_s is not None else None,
        retry_options=types.HttpRetryOptions(attempts=1),
    )


def to_content(message: ChatMessage) -> Any:
    """Neutral chat turn -> Gemini Content (a model turn is sent back exactly as received)."""
    if message.role == "model" and message.raw is not None:
        return message.raw
    if message.role == "tool":
        return types.Content(role="user", parts=[
            types.Part.from_function_response(name=name, response=result) for name, result in message.results
        ])
    if message.role == "model":
        parts = [types.Part(function_call=types.FunctionCall(name=c.name, args=c.args)) for c in message.calls]
        return types.Content(role="model", parts=parts or [types.Part.from_text(text=message.text or "")])
    return types.Content(role="user", parts=[types.Part.from_text(text=message.text or "")])
