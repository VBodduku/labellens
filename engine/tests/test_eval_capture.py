"""Transport tests use fake HTTP responses; none measure real-packet accuracy."""

import json
from io import BytesIO
from pathlib import Path
from urllib.error import URLError

import pytest
from pydantic import TypeAdapter
from shared.contract import Profile, ScanResult
from engine.eval import live


def scan():
    result = ScanResult.model_validate_json(
        Path("shared/fixtures/scan_result.json").read_text()
    )
    result.extraction.meta.provider = "gemini"
    return result


def profiles():
    return TypeAdapter(list[Profile]).validate_json(
        Path("engine/eval/eval_profiles.json").read_text()
    )


def case(tmp_path):
    folder = tmp_path / "001_test_clean"
    folder.mkdir()
    (folder / "img_0.jpg").write_bytes(b"test image bytes, transport only")
    return live.CaptureCase(folder, "real")


def fake_http(monkeypatch, response=None, mode="real", fail=False):
    calls = []
    health = dict(
        status="ok", providers={"gemini": True, "ollama": False}, engine_mode=mode
    )
    # Keep the complete, actual health contract rather than a transport-only shape.
    from shared.contract import HealthResponse

    health = HealthResponse.model_validate(health).model_dump_json().encode()

    def urlopen(request, timeout):
        calls.append((request, timeout))
        if request.full_url.endswith("/api/health"):
            return BytesIO(health)
        if fail:
            raise URLError("deliberate network failure")
        return BytesIO(
            response if response is not None else scan().model_dump_json().encode()
        )

    monkeypatch.setattr(live, "urlopen", urlopen)
    return calls


def test_live_capture_saves_full_response_manifest_and_multipart(tmp_path, monkeypatch):
    packet = case(tmp_path)
    calls = fake_http(monkeypatch)
    output = tmp_path / "responses"
    live.capture("http://localhost:8000/", [packet], output, profiles(), timeout=45)
    assert len(calls) == 2
    request, timeout = calls[1]
    assert request.method == "POST" and timeout == 45
    assert b'name="images"; filename="img_0.jpg"' in request.data
    assert b'name="profiles"' in request.data and b'name="lang"' in request.data
    saved = ScanResult.model_validate_json((output / "001_test_clean.json").read_text())
    assert saved.extraction.meta.provider == "gemini"
    manifest = json.loads((output / "capture_manifest.json").read_text())
    assert manifest["failed"] == [] and manifest["engine_mode"] == "real"


def test_stub_backend_is_rejected_before_scan(tmp_path, monkeypatch):
    packet = case(tmp_path)
    calls = fake_http(monkeypatch, mode="stub")
    with pytest.raises(live.CaptureError, match="ENGINE_MODE=real"):
        live.capture(
            "http://localhost:8000", [packet], tmp_path / "responses", profiles()
        )
    assert len(calls) == 1


@pytest.mark.parametrize("failure", ["network", "invalid_json", "fixture"])
def test_capture_failure_has_manifest_and_never_becomes_success(
    tmp_path, monkeypatch, failure
):
    packet = case(tmp_path)
    response = b"invalid" if failure == "invalid_json" else None
    if failure == "fixture":
        result = scan()
        result.extraction.meta.provider = "fixture"
        response = result.model_dump_json().encode()
    fake_http(monkeypatch, response=response, fail=failure == "network")
    output = tmp_path / "responses"
    with pytest.raises(live.CaptureError, match="Capture failed"):
        live.capture("http://localhost:8000", [packet], output, profiles())
    assert json.loads((output / "capture_manifest.json").read_text())["failed"] == [
        packet.folder.name
    ]
    assert not (output / f"{packet.folder.name}.json").exists()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_bad_timeout_fails_without_network(tmp_path, value):
    with pytest.raises(ValueError, match="timeout"):
        live.capture(
            "http://localhost:8000",
            [case(tmp_path)],
            tmp_path / "responses",
            profiles(),
            value,
        )


@pytest.mark.parametrize(
    "url",
    ["file:///tmp/x", "localhost:8000", "https://u:p@example.com", "http://x/?q=1"],
)
def test_bad_backend_url_rejected(url):
    with pytest.raises(ValueError, match="http"):
        live._base_url(url)


@pytest.mark.parametrize(
    "names", [[], ["img_1.jpg"], ["img_0.jpg", "img_0.png"], ["img_0.jpg", "img_3.jpg"]]
)
def test_invalid_panel_layouts_rejected(tmp_path, names):
    for name in names:
        (tmp_path / name).write_bytes(b"photo")
    with pytest.raises(ValueError):
        live.images_for_case(tmp_path)


@pytest.mark.parametrize("size", [0, 400 * 1024 + 1])
def test_invalid_image_size_rejected(tmp_path, size):
    (tmp_path / "img_0.jpg").write_bytes(b"x" * size)
    with pytest.raises(ValueError, match="400 KB"):
        live.images_for_case(tmp_path)
