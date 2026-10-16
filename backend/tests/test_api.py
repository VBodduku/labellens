from __future__ import annotations

import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app import fixtures
from shared.contract import (
    AskResponse,
    ErrorResponse,
    ExplainResponse,
    HealthResponse,
    ProfileParseResponse,
    RestrictionCatalogItem,
    ScanResult,
)
from shared.engine_stub import restriction_catalog

PROFILES_JSON = (fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8")


def png(size: tuple[int, int] = (800, 1000)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 200, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def files(*blobs: bytes, name: str = "label.png", mime: str = "image/png") -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("images", (f"{i}_{name}", blob, mime)) for i, blob in enumerate(blobs)]


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    body = ErrorResponse.model_validate(response.json())
    assert body.error_code == code and body.message


# ---------------------------------------------------------------- health / catalog
def test_health_reports_degraded_when_no_provider(client: TestClient) -> None:
    body = HealthResponse.model_validate(client.get("/api/health").json())
    assert body.status == "degraded"
    assert body.providers == {"gemini": False, "ollama": False}
    assert body.engine_mode == "stub"


def test_health_ok_when_a_provider_is_up(client: TestClient, providers: dict[str, bool]) -> None:
    providers["ollama"] = True
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["providers"] == {"gemini": False, "ollama": True}


def test_health_hides_reachable_provider_without_a_configured_client(
    client: TestClient, providers: dict[str, bool],
) -> None:
    providers["gemini"] = True          # reachable, but the router has no Gemini client (no key)
    assert client.get("/api/health").json()["providers"]["gemini"] is False


def test_catalog_comes_from_engine(client: TestClient) -> None:
    response = client.get("/api/catalog")
    assert response.status_code == 200
    items = [RestrictionCatalogItem.model_validate(i) for i in response.json()]
    assert [i.key for i in items] == [i.key for i in restriction_catalog()]


# ---------------------------------------------------------------- scan
def test_scan_returns_scan_result_in_requested_lang(client: TestClient, label_png: bytes) -> None:
    response = client.post("/api/scan", files=files(label_png),
                           data={"profiles": PROFILES_JSON, "lang": "te", "panel_hints": '["back"]'})
    assert response.status_code == 200, response.text
    result = ScanResult.model_validate(response.json())
    assert result.lang == "te"
    assert result.extraction.ocr_tokens
    assert result.extraction.images[0].panel_hint == "back"
    assert [r.profile_id for r in result.reports] == ["p_aarav", "p_thatha", "p_lakshmi"]


def test_scan_accepts_max_images(client: TestClient, label_png: bytes) -> None:
    response = client.post("/api/scan", files=files(label_png, label_png, label_png), data={"profiles": "[]"})
    assert response.status_code == 200, response.text
    assert [i.image_id for i in ScanResult.model_validate(response.json()).extraction.images] == [
        "img_0", "img_1", "img_2"]


def test_scan_with_nothing_readable_is_bad_image(client: TestClient) -> None:
    response = client.post("/api/scan", files=files(png()), data={"profiles": "[]"})
    assert_error(response, 422, "BAD_IMAGE")


def test_scan_without_images_is_validation_error(client: TestClient) -> None:
    assert_error(client.post("/api/scan", data={"profiles": "[]"}), 400, "VALIDATION")


def test_scan_with_too_many_images(client: TestClient) -> None:
    response = client.post("/api/scan", files=files(png(), png(), png(), png()), data={"profiles": "[]"})
    assert_error(response, 400, "TOO_MANY_IMAGES")


def test_scan_rejects_oversized_image(client: TestClient) -> None:
    big = png() + b"\0" * (1024 * 1024)   # MAX_IMAGE_MB=1 in tests
    assert_error(client.post("/api/scan", files=files(big), data={"profiles": "[]"}), 413, "BAD_IMAGE")


def test_scan_rejects_oversized_body(client: TestClient) -> None:
    blobs = [b"\0" * (1400 * 1024)] * 3      # 4.1 MB > 3 x 1 MB + 1 MB body limit
    response = client.post("/api/scan", files=files(*blobs), data={"profiles": "[]"})
    assert_error(response, 413, "BAD_IMAGE")


def test_scan_rejects_non_image(client: TestClient) -> None:
    response = client.post("/api/scan", files=files(b"hello", name="notes.txt", mime="text/plain"),
                           data={"profiles": "[]"})
    assert_error(response, 422, "BAD_IMAGE")
    assert "Photo 1" in response.json()["message"]


@pytest.mark.parametrize("data", [
    {"profiles": "not json"},
    {"profiles": '[{"name": "no id"}]'},
    {"profiles": "[]", "lang": "fr"},
    {"profiles": "[]", "panel_hints": '["top"]'},
    {"profiles": "[]", "panel_hints": '["front", "back"]'},
    {},
])
def test_scan_rejects_bad_form_fields(client: TestClient, data: dict[str, str]) -> None:
    assert_error(client.post("/api/scan", files=files(png()), data=data), 400, "VALIDATION")


# ---------------------------------------------------------------- recheck
def test_recheck_runs_engine_on_posted_extraction(client: TestClient) -> None:
    extraction = fixtures.scan_result().extraction
    body = {"extraction": extraction.model_dump(), "profiles": json.loads(PROFILES_JSON), "lang": "hi"}
    response = client.post("/api/recheck", json=body)
    assert response.status_code == 200, response.text
    result = ScanResult.model_validate(response.json())
    assert result.lang == "hi"
    assert result.scan_id == extraction.scan_id
    assert [r.profile_id for r in result.reports] == ["p_aarav", "p_thatha", "p_lakshmi"]
    assert all(r.results[0].explanation.startswith("[stub]") for r in result.reports)


def test_recheck_rejects_malformed_body(client: TestClient) -> None:
    assert_error(client.post("/api/recheck", json={"profiles": []}), 400, "VALIDATION")
    assert_error(client.post("/api/recheck", content=b"{not json", headers={"content-type": "application/json"}),
                 400, "VALIDATION")


# ---------------------------------------------------------------- ask / parse / explain
def test_ask_returns_fixture_in_requested_lang(client: TestClient) -> None:
    body = {"question": "Is this okay for Thatha?", "lang": "te",
            "scan": fixtures.scan_result().model_dump(), "profiles": json.loads(PROFILES_JSON)}
    response = client.post("/api/ask", json=body)
    assert response.status_code == 200
    answer = AskResponse.model_validate(response.json())
    assert answer.lang == "te" and answer.tool_calls


def test_ask_rejects_missing_scan(client: TestClient) -> None:
    assert_error(client.post("/api/ask", json={"question": "hi", "profiles": []}), 400, "VALIDATION")


def test_profile_parse_returns_fixture(client: TestClient) -> None:
    response = client.post("/api/profile/parse", json={"text": "My son is allergic to peanuts", "lang": "en"})
    assert response.status_code == 200
    assert ProfileParseResponse.model_validate(response.json()).needs_confirmation is True
    assert_error(client.post("/api/profile/parse", json={"lang": "en"}), 400, "VALIDATION")


def test_explain_returns_fixture(client: TestClient) -> None:
    response = client.post("/api/explain", json={"term": "INS 322"})
    assert response.status_code == 200
    ExplainResponse.model_validate(response.json())
    assert_error(client.post("/api/explain", json={"term": "x", "lang": "de"}), 400, "VALIDATION")


# ---------------------------------------------------------------- cross-cutting
def test_unknown_route_is_error_response(client: TestClient) -> None:
    assert_error(client.get("/api/nope"), 404, "NOT_FOUND")


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    assert client.get("/api/catalog", headers={"X-Request-ID": "abc123"}).headers["X-Request-ID"] == "abc123"
    assert len(client.get("/api/catalog").headers["X-Request-ID"]) == 32


def test_cors_preflight_allows_frontend_origin(client: TestClient) -> None:
    response = client.options("/api/scan", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unexpected_error_becomes_internal_without_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom() -> None:
        raise RuntimeError("secret internals")

    monkeypatch.setattr("backend.app.engine_adapter.restriction_catalog", boom)
    response = client.get("/api/catalog")
    assert_error(response, 500, "INTERNAL")
    assert "secret" not in response.text
