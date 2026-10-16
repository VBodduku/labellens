"""Logs never contain API keys, images or prompts."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from backend.app.cache import get_cache
from backend.app.config import get_settings
from backend.app.llm import router as router_module
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.router import get_router
from backend.app.logging_setup import JsonFormatter
from backend.app.main import create_app
from backend.tests import fixture_data

SECRET = "AIzaTESTSECRETdoNotLog1234567890abcdefg"


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.setFormatter(JsonFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def logged(monkeypatch: pytest.MonkeyPatch, providers: dict[str, bool], cache) -> Iterator[tuple[TestClient, Collect]]:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("GEMINI_API_KEY", SECRET)
    monkeypatch.setenv("LOG_LEVEL", "debug")
    get_settings.cache_clear()
    router_module.get_router.cache_clear()

    class RejectingSdk:
        class aio:
            class models:
                @staticmethod
                async def generate_content(**kwargs):  # type: ignore[no-untyped-def]
                    raise errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                                             "message": "API key not valid."}})

    monkeypatch.setattr(GeminiClient, "_client", lambda self: RejectingSdk)
    app = create_app()
    app.dependency_overrides[get_cache] = lambda: cache
    collector = Collect()
    with TestClient(app) as client:
        for name in ("labellens", ""):
            logging.getLogger(name).addHandler(collector)
        try:
            yield client, collector
        finally:
            for name in ("labellens", ""):
                logging.getLogger(name).removeHandler(collector)
    router_module.get_router.cache_clear()


def test_no_secrets_images_or_prompts_in_logs(logged: tuple[TestClient, Collect], label_png: bytes) -> None:
    client, collector = logged
    profiles = json.dumps(fixture_data.profiles_json())
    scan = client.post("/api/scan", files=[("images", ("l.png", label_png, "image/png"))], data={"profiles": profiles})
    assert scan.status_code == 200
    client.post("/api/ask", json={"question": "Is this okay for Aarav?", "scan": scan.json(),
                                  "profiles": json.loads(profiles)})
    client.post("/api/explain", json={"term": "Zorbex"})
    client.get("/api/health")
    assert any('"route": "/api/scan"' in line for line in collector.lines)
    assert any("gemini HTTP 400" in line for line in collector.lines)          # failures are visible ...
    for line in collector.lines:                                              # ... secrets and payloads are not
        assert SECRET not in line
        assert "TRANSCRIBE the label" not in line and "iVBORw0KGgo" not in line and "/9j/" not in line
        assert len(line) < 2000
    assert get_router is router_module.get_router
