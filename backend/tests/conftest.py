from __future__ import annotations

import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import provider_probe
from backend.app.config import get_settings
from backend.app.main import create_app
from backend.scripts.make_test_label import fixture_tokens, render_label

TEST_ENV = {
    "ENGINE_MODE": "stub",
    "MAX_IMAGES": "3",
    "MAX_IMAGE_MB": "1",
    "GEMINI_API_KEY": "",
    "GEMINI_API_KEY_BACKUP": "",
    "CORS_ORIGINS": "http://localhost:5173",
    "LOG_LEVEL": "warning",
}


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in TEST_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    provider_probe.reset_cache()
    yield
    get_settings.cache_clear()
    provider_probe.reset_cache()


@pytest.fixture
def providers(monkeypatch: pytest.MonkeyPatch) -> dict[str, bool]:
    """Offline provider status; tests flip the values they need."""
    status = {"gemini": False, "ollama": False}

    async def fake_probe(_: object) -> dict[str, bool]:
        return dict(status)

    monkeypatch.setattr("backend.app.api.routes_misc.probe_providers", fake_probe)
    return status


@pytest.fixture
def client(providers: dict[str, bool]) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def label_image() -> Image.Image:
    tokens, size = fixture_tokens()
    return render_label(tokens, size)


@pytest.fixture(scope="session")
def label_png(label_image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    label_image.save(buffer, format="PNG")
    return buffer.getvalue()
