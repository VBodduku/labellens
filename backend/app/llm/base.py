"""Provider-neutral LLM types: the client protocol, image parts and the error hierarchy."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ProviderName = Literal["gemini", "ollama"]
# User-facing prose (summaries, explanations, translations) is only taken from these providers:
# a small local model misstates facts and verdict words in hi/te, and nothing can check prose.
PROSE_PROVIDERS: tuple[ProviderName, ...] = ("gemini",)


@dataclass(frozen=True)
class LLMImage:
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]          # JSON schema of the arguments


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class ChatMessage:
    """Provider-neutral chat turn. `raw` keeps the provider's own reply (e.g. Gemini thought signatures)."""
    role: Literal["user", "model", "tool"]
    text: str | None = None
    calls: list[ToolCall] = field(default_factory=list)
    results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)   # tool name, result
    raw: Any = None


class ToolChatClient(Protocol):
    label: str
    model: str

    async def chat_with_tools(
        self, messages: list[ChatMessage], tools: list[ToolSpec], system: str, timeout_s: float,
    ) -> ChatMessage:
        """One model turn: either tool calls or a final text answer."""
        ...


class LLMClient(Protocol):
    name: ProviderName
    label: str                  # distinguishes clients of one provider, e.g. "gemini:backup"
    model: str

    async def generate_json(
        self, prompt: str, images: list[LLMImage], schema: dict[str, Any], timeout_s: float,
    ) -> str:
        """Return the model's raw JSON text constrained to `schema`."""
        ...


class LLMError(Exception):
    """Base class for provider failures. Messages never contain prompts, images or keys."""


class RateLimitedError(LLMError):
    def __init__(self, retry_after_s: int, message: str = "rate limited") -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class ProviderUnavailableError(LLMError):
    """Network failure, timeout, auth problem or server error."""


class InvalidOutputError(LLMError):
    """The provider answered, but not with usable JSON."""
