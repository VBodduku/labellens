"""Gemini and Ollama clients: request shape and error mapping, fully offline."""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx
import pytest
from google.genai import errors

from backend.app.llm.base import InvalidOutputError, LLMImage, ProviderUnavailableError, RateLimitedError
from backend.app.llm.gemini import GeminiClient, retry_after_from
from backend.app.llm.ollama import OllamaClient

IMAGE = LLMImage("image/jpeg", b"\xff\xd8jpeg")
SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


class FakeModels:
    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


class FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


def gemini_with(monkeypatch: pytest.MonkeyPatch, outcome: Any) -> tuple[GeminiClient, FakeModels]:
    client = GeminiClient("test-key", "gemini-flash-latest")
    models = FakeModels(outcome)
    fake = type("FakeClient", (), {"aio": type("Aio", (), {"models": models})()})()
    monkeypatch.setattr(client, "_client", lambda: fake)
    return client, models


def test_gemini_request_is_schema_constrained_and_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    client, models = gemini_with(monkeypatch, FakeResponse('{"a": "b"}'))
    assert asyncio.run(client.generate_json("read this", [IMAGE], SCHEMA, 10)) == '{"a": "b"}'
    [call] = models.calls
    config = call["config"]
    assert call["model"] == "gemini-flash-latest"
    assert config.temperature == 0
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == SCHEMA
    assert call["contents"][-1] == "read this"
    assert call["contents"][0].inline_data.data == IMAGE.data


def test_gemini_sdk_client_is_reused_and_has_no_retries() -> None:
    client = GeminiClient("k", "m")
    assert client._client() is client._client()
    options = client._client()._api_client._http_options
    assert options.retry_options is not None and options.retry_options.attempts == 1


def test_gemini_request_carries_its_own_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client, models = gemini_with(monkeypatch, FakeResponse('{"a": "b"}'))
    asyncio.run(client.generate_json("p", [], SCHEMA, 25.5))
    options = models.calls[0]["config"].http_options
    assert options.timeout == 25500 and options.retry_options.attempts == 1
    asyncio.run(client.generate_json("p", [], SCHEMA, 4))                # Google's minimum deadline is 10 s
    assert models.calls[1]["config"].http_options.timeout == 15000


def test_gemini_429_becomes_rate_limited_with_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    body = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "quota", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}]}}
    client, _ = gemini_with(monkeypatch, errors.ClientError(429, body))
    with pytest.raises(RateLimitedError) as info:
        asyncio.run(client.generate_json("p", [], SCHEMA, 10))
    assert info.value.retry_after_s == 17


@pytest.mark.parametrize("outcome", [
    errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "busy"}}),
    errors.ClientError(403, {"error": {"code": 403, "status": "PERMISSION_DENIED", "message": "bad key"}}),
    httpx.ReadTimeout("slow"),
    RuntimeError("Cannot send a request, as the client has been closed."),
    ValueError("unexpected SDK state"),
])
def test_gemini_failures_become_unavailable(monkeypatch: pytest.MonkeyPatch, outcome: BaseException) -> None:
    client, _ = gemini_with(monkeypatch, outcome)
    with pytest.raises(ProviderUnavailableError) as info:
        asyncio.run(client.generate_json("p", [], SCHEMA, 10))
    assert "test-key" not in str(info.value)


def test_gemini_empty_text_is_invalid_output(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = gemini_with(monkeypatch, FakeResponse(None))
    with pytest.raises(InvalidOutputError):
        asyncio.run(client.generate_json("p", [], SCHEMA, 10))


def test_retry_delay_parsing_defaults() -> None:
    assert retry_after_from({"error": {"details": [{"retryDelay": "2.4s"}]}}) == 2
    assert retry_after_from({"error": {"details": []}}) == 60
    assert retry_after_from(None) == 60


def ollama_with(handler: Any) -> OllamaClient:
    return OllamaClient("http://ollama.test:11434/", "gemma3:4b", transport=httpx.MockTransport(handler))


def test_ollama_request_has_images_schema_and_temperature() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://ollama.test:11434/api/chat"
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": '{"a": "b"}'}})

    assert asyncio.run(ollama_with(handler).generate_json("read", [IMAGE], SCHEMA, 10)) == '{"a": "b"}'
    [payload] = seen
    assert payload["model"] == "gemma3:4b" and payload["stream"] is False
    assert payload["format"] == SCHEMA
    assert payload["options"]["temperature"] == 0
    assert payload["messages"][0]["images"] == [base64.b64encode(IMAGE.data).decode()]
    assert payload["messages"][0]["content"] == "read"


@pytest.mark.parametrize("response, error", [
    (httpx.Response(500, text="boom"), ProviderUnavailableError),
    (httpx.Response(200, json={"error": "x"}), InvalidOutputError),
    (httpx.Response(200, json={"message": {"content": "  "}}), InvalidOutputError),
])
def test_ollama_errors(response: httpx.Response, error: type[Exception]) -> None:
    with pytest.raises(error):
        asyncio.run(ollama_with(lambda request: response).generate_json("p", [], SCHEMA, 10))


def test_ollama_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(ProviderUnavailableError):
        asyncio.run(ollama_with(handler).generate_json("p", [], SCHEMA, 10))
