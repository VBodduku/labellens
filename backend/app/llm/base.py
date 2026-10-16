"""Provider-neutral LLM types: the client protocol, image parts and the error hierarchy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

ProviderName = Literal["gemini", "ollama"]


@dataclass(frozen=True)
class LLMImage:
    mime_type: str
    data: bytes


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
