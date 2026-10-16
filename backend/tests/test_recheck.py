"""/api/scan summaries and /api/recheck summary reuse (spec §6)."""
from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient

from backend.app.wording import STATE_WORDS
from backend.tests import fixture_data as fixtures
from backend.tests.fakes import SUMMARIZE, FakeLLM, recorded, scan_llm
from shared.contract import ScanResult

PROFILES = json.loads((fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))


@pytest.fixture
def llm() -> FakeLLM:
    """Summaries come only from Gemini, so the scan model here is Gemini-named."""
    return scan_llm(recorded("ollama_test_label.json"), name="gemini", model="gemini-test")


def summaries(lang_word: str, lang: str = "en") -> str:
    states = " / ".join(STATE_WORDS[lang].values())     # contains whichever overall word applies
    return json.dumps({"summaries": [
        {"profile_id": p["profile_id"], "summary": f"{lang_word} summary for {p['name']}: {states}"}
        for p in PROFILES]})


def expected(lang_word: str, lang: str = "en") -> list[str]:
    states = " / ".join(STATE_WORDS[lang].values())
    return [f"{lang_word} summary for {p['name']}: {states}" for p in PROFILES]


def scan(client: TestClient, png: bytes, lang: str = "en") -> ScanResult:
    response = client.post("/api/scan", files=[("images", ("l.png", io.BytesIO(png), "image/png"))],
                           data={"profiles": json.dumps(PROFILES), "lang": lang})
    assert response.status_code == 200, response.text
    return ScanResult.model_validate(response.json())


def recheck(client: TestClient, result: ScanResult, lang: str, profiles: list | None = None) -> ScanResult:
    body = {"extraction": result.extraction.model_dump(), "profiles": profiles or PROFILES, "lang": lang}
    response = client.post("/api/recheck", json=body)
    assert response.status_code == 200, response.text
    return ScanResult.model_validate(response.json())


def test_scan_fills_summaries(client: TestClient, llm: FakeLLM, label_png: bytes) -> None:
    llm.routes[SUMMARIZE] = [summaries("English")]
    result = scan(client, label_png)
    assert [r.summary for r in result.reports] == expected("English")
    assert all(r.summary_lang == "en" for r in result.reports)


def test_recheck_same_lang_reuses_summaries_without_llm(client: TestClient, llm: FakeLLM, label_png: bytes) -> None:
    llm.routes[SUMMARIZE] = [summaries("English")]
    result = scan(client, label_png)
    again = recheck(client, result, "en")
    assert [r.summary for r in again.reports] == [r.summary for r in result.reports]
    assert len(llm.calls(SUMMARIZE)) == 1


def test_recheck_with_changed_verdict_drops_that_summary(client: TestClient, llm: FakeLLM, label_png: bytes) -> None:
    llm.routes[SUMMARIZE] = [summaries("English")]
    result = scan(client, label_png)
    changed = json.loads(json.dumps(PROFILES))
    changed[0]["restrictions"] = [r for r in changed[0]["restrictions"] if r["key"] != "peanut"]
    again = recheck(client, result, "en", changed)
    by_id = {r.profile_id: r.summary for r in again.reports}
    assert by_id["p_aarav"] is None and by_id["p_thatha"] == expected("English")[1]


def test_recheck_new_lang_regenerates(client: TestClient, llm: FakeLLM, label_png: bytes) -> None:
    llm.routes[SUMMARIZE] = [summaries("English"), summaries("Telugu", "te")]
    result = scan(client, label_png)
    again = recheck(client, result, "te")
    assert again.lang == "te"
    assert [r.summary for r in again.reports] == expected("Telugu", "te")
    assert len(llm.calls(SUMMARIZE)) == 2


def test_recheck_of_unknown_scan_has_no_summaries(client: TestClient) -> None:
    result = recheck(client, fixtures.scan_result(), "en")
    assert all(r.summary is None for r in result.reports)
    assert any(u.message_key == "unknown.retake_region" and u.region is not None for u in result.unknowns)
