"""Phase 4 hardening: odd images, body limits, structured errors, degraded LLM/OCR paths."""
from __future__ import annotations

import asyncio
import io
import json
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.cache import ExtractionCache
from backend.app.llm.base import ProviderUnavailableError
from backend.app.pipeline import ocr, orchestrator
from backend.app.pipeline.images import BadImageError, decode_upload
from backend.app.pipeline.orchestrator import ScanInput, run_scan
from backend.tests import fixture_data
from backend.tests.fakes import STRUCTURE, FakeLLM, router_with
from shared.contract import ImageQuality, ScanResult

EXIF_ORIENTATION = 0x0112


def encode(image: Image.Image, fmt: str, **kwargs: object) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format=fmt, **kwargs)
    return buffer.getvalue()


def post_scan(client: TestClient, data: bytes, name: str = "photo.jpg", mime: str = "image/jpeg"):  # type: ignore[no-untyped-def]
    return client.post("/api/scan", files=[("images", (name, data, mime))],
                       data={"profiles": json.dumps(fixture_data.profiles_json())})


# ---------------------------------------------------------------- images
def test_heic_photo_is_decoded() -> None:
    data = encode(Image.new("RGB", (900, 700), (200, 180, 160)), "HEIF")
    image = decode_upload(data, "img_0")
    assert (image.width, image.height) == (900, 700)


def test_huge_image_is_rejected_before_decoding() -> None:
    data = encode(Image.new("1", (8000, 7000)), "PNG")         # 56 MP, tiny file
    with pytest.raises(BadImageError, match="too many pixels"):
        decode_upload(data, "img_0")


def test_big_jpeg_decodes_at_reduced_scale_and_keeps_original_size_with_exif() -> None:
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6
    data = encode(Image.new("RGB", (4000, 3000), "white"), "JPEG", exif=exif)
    started = time.perf_counter()
    image = decode_upload(data, "img_0")
    assert time.perf_counter() - started < 1.0
    assert (image.original_width, image.original_height) == (3000, 4000)
    assert max(image.width, image.height) == 2000 and image.height > image.width


def test_tiny_photo_is_rejected_as_unreadable(client: TestClient) -> None:
    response = post_scan(client, encode(Image.new("RGB", (60, 40), "white"), "PNG"), "t.png", "image/png")
    assert response.status_code == 422 and response.json()["error_code"] == "BAD_IMAGE"


def test_exif_rotated_label_is_read_upright(client: TestClient, label_image: Image.Image) -> None:
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = 6                                   # viewer rotates 90 degrees clockwise
    stored = label_image.rotate(90, expand=True)                # pixels saved on their side
    response = post_scan(client, encode(stored, "JPEG", quality=95, exif=exif))
    assert response.status_code == 200, response.text
    extraction = ScanResult.model_validate(response.json()).extraction
    assert (extraction.images[0].width, extraction.images[0].height) == (1000, 1400)
    assert any(t.text.startswith("INGREDIENTS") for t in extraction.ocr_tokens)


# ---------------------------------------------------------------- request limits and errors
def chunks(data: bytes, size: int = 64 * 1024) -> Iterator[bytes]:
    for start in range(0, len(data), size):
        yield data[start:start + size]


def test_chunked_upload_without_length_is_limited(client: TestClient) -> None:
    boundary = "xyzBOUNDARY"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"profiles\"\r\n\r\n[]\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"images\"; filename=\"a.jpg\"\r\n"
            f"Content-Type: image/jpeg\r\n\r\n").encode() + b"\0" * (5 * 1024 * 1024) + f"\r\n--{boundary}--\r\n".encode()
    response = client.post("/api/scan", content=chunks(body),
                           headers={"content-type": f"multipart/form-data; boundary={boundary}"})
    assert response.status_code == 413 and response.json()["error_code"] == "BAD_IMAGE"
    assert "x-request-id" in response.headers


def test_oversized_json_body_is_limited(client: TestClient) -> None:
    body = json.dumps({"question": "x" * (5 * 1024 * 1024)}).encode()
    response = client.post("/api/ask", content=chunks(body), headers={"content-type": "application/json"})
    assert response.status_code == 413 and response.json()["error_code"] == "VALIDATION"


@pytest.mark.parametrize("method, path, kwargs, status", [
    ("GET", "/api/scan", {}, 405),
    ("POST", "/api/scan", {"content": b"--x\r\ngarbage", "headers": {"content-type": "multipart/form-data; boundary=x"}}, 400),
    ("POST", "/api/ask", {"content": b"not json", "headers": {"content-type": "application/json"}}, 400),
    ("POST", "/api/explain", {"content": b"[1, 2]", "headers": {"content-type": "application/json"}}, 400),
])
def test_bad_requests_get_structured_errors(client: TestClient, method: str, path: str, kwargs: dict, status: int) -> None:
    response = client.request(method, path, **kwargs)
    assert response.status_code == status
    assert set(response.json()) == {"error_code", "message", "retry_after_s"}


# ---------------------------------------------------------------- degraded LLM / OCR
def scan_input(png: bytes) -> ScanInput:
    return ScanInput(images=[decode_upload(png, "img_0")], raw=[png], hints=[], profiles=fixture_data.profiles(),
                     lang="en")


def test_gemini_invalid_json_twice_then_no_ollama_still_answers(label_png: bytes, cache: ExtractionCache) -> None:
    gemini = FakeLLM(routes={STRUCTURE: ["not json at all", '{"panels": "still wrong"}']})
    ollama = FakeLLM([ProviderUnavailableError("down")], name="ollama")
    result = asyncio.run(run_scan(scan_input(label_png), router_with(gemini, ollama), cache))
    assert result.extraction.meta.provider == "ocr_only" and len(gemini.calls(STRUCTURE)) == 2
    assert result.extraction.ingredients


@pytest.fixture
def no_ocr_text(monkeypatch: pytest.MonkeyPatch) -> None:
    async def nothing(image):  # type: ignore[no-untyped-def]
        return []

    monkeypatch.setattr(orchestrator, "run_ocr", nothing)
    monkeypatch.setattr(orchestrator, "assess",
                        lambda image: ImageQuality(ok=True, blur_score=500, glare_ratio=0, brightness=150))


def boxed_answer() -> str:
    section = {"presence": "found", "complete": True, "issues": [], "unreadable_token_ids": [], "unreadable_boxes": []}
    none = {**section, "presence": "not_found", "complete": False}
    return json.dumps({"product_name": None, "languages": ["hi"], "panels": [{
        "image_id": "img_0", "panel": "back",
        "ingredients": [{"text": "चीनी", "token_ids": [], "percentage": None, "parent_index": None,
                         "readability": "clear", "box_2d": [200, 60, 220, 150]}],
        "ingredients_section": section, "allergen_statements": [], "allergen_section": none,
        "nutrition": None, "nutrition_section": none, "veg_mark": {"value": "veg", "box_2d": [20, 860, 70, 940]},
        "claims": []}]})


def test_no_ocr_text_but_llm_reads_the_photo_gives_approximate_evidence(
    no_ocr_text: None, label_png: bytes, cache: ExtractionCache,
) -> None:
    result = asyncio.run(run_scan(scan_input(label_png), router_with(FakeLLM(routes={STRUCTURE: [boxed_answer()]})),
                                  cache))
    [sugar] = result.extraction.ingredients
    assert sugar.evidence[0].status == "approximate" and sugar.evidence[0].box is not None
    assert result.extraction.ocr_tokens == []


def test_no_ocr_text_and_no_llm_is_an_honest_empty_reading(
    no_ocr_text: None, label_png: bytes, cache: ExtractionCache,
) -> None:
    result = asyncio.run(run_scan(scan_input(label_png), router_with(FakeLLM([ProviderUnavailableError("down")])),
                                  cache))
    e = result.extraction
    assert e.meta.provider == "ocr_only" and e.ingredients == []
    assert e.ingredients_section.presence == "not_found" and not e.ingredients_section.complete
    assert all(r.state != "not_listed" or r.reason_code != "NOT_LISTED_COMPLETE"
               for report in result.reports for r in report.results)


def test_stuck_ocr_times_out_with_no_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    def stuck(image, image_id):  # type: ignore[no-untyped-def]
        time.sleep(0.5)
        return ["never"]

    monkeypatch.setattr(ocr, "ocr_image", stuck)
    tokens = asyncio.run(ocr.ocr_image_async(Image.new("RGB", (10, 10)), "img_0", timeout_s=0.05))
    assert tokens == []


def test_ocr_model_is_loaded_once(client: TestClient) -> None:
    assert ocr.get_engine() is ocr.get_engine()
    assert ocr.get_engine.cache_info().currsize == 1


def test_cache_hit_reuses_interpretations_and_summaries_without_llm(label_png: bytes, cache: ExtractionCache) -> None:
    from backend.app.wording import STATE_WORDS
    from backend.tests.fakes import INTERPRET, SUMMARIZE, recorded, scan_llm

    words = " / ".join(STATE_WORDS["en"].values())
    summaries = json.dumps({"summaries": [{"profile_id": p["profile_id"], "summary": f"Summary: {words}"}
                                          for p in fixture_data.profiles_json()]})
    llm = scan_llm(recorded("ollama_test_label.json"), name="gemini", summarize=[summaries],
                   interpret=['{"interpretations": []}'])
    first = asyncio.run(run_scan(scan_input(label_png), router_with(llm), cache))
    calls = len(llm.prompts)
    started = time.perf_counter()
    second = asyncio.run(run_scan(scan_input(label_png), router_with(llm), cache))
    assert time.perf_counter() - started < 1.5
    assert second.extraction.meta.cache_hit and len(llm.prompts) == calls
    assert [r.summary for r in second.reports] == [r.summary for r in first.reports]
    assert len(llm.calls(SUMMARIZE)) == 1 and len(llm.calls(INTERPRET)) == 1


# ---------------------------------------------------------------- truthful health
def test_probe_reports_invalid_key_and_missing_ollama_as_down(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    from backend.app import provider_probe
    from backend.app.config import get_settings

    async def fake_get(self, url, headers=None):  # type: ignore[no-untyped-def]
        if "generativelanguage" in str(url):
            status = 200 if (headers or {}).get("x-goog-api-key") == "AIzaGOOD" else 400
            return httpx.Response(status)
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    get_settings.cache_clear()
    provider_probe.reset_cache()
    assert asyncio.run(provider_probe.probe_providers(get_settings())) == {"gemini": False, "ollama": False}
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaGOOD")
    get_settings.cache_clear()
    provider_probe.reset_cache()
    assert asyncio.run(provider_probe.probe_providers(get_settings())) == {"gemini": True, "ollama": False}


def test_health_hides_a_rate_limited_gemini(client: TestClient, providers: dict[str, bool]) -> None:
    from backend.app.llm.router import LLMRouter, get_router

    limited = LLMRouter([FakeLLM([ProviderUnavailableError("x")], label="gemini:primary")], 5)
    limited.report_rate_limit("gemini:primary", 60)
    client.app.dependency_overrides[get_router] = lambda: limited  # type: ignore[attr-defined]
    providers["gemini"] = True
    body = client.get("/api/health").json()
    assert body["providers"]["gemini"] is False and body["status"] == "degraded"
