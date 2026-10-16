"""Opt-in: real Gemini on the rendered fixture label. Run with `python -m pytest backend/tests -m live`."""
from __future__ import annotations

import asyncio
import os

import pytest
from dotenv import dotenv_values
from PIL import Image

from backend.app import engine_adapter
from backend.app.agent import agent
from backend.app.config import REPO_ROOT
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.router import LLMRouter
from backend.app.pipeline.align import TokenIndex, align_panel
from backend.app.pipeline.assemble import build_scan_result
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.structure import structure
from backend.tests import fixture_data
from shared.contract import AskRequest, OcrToken

pytestmark = pytest.mark.live
LIVE_TIMEOUT_S = 60


def gemini() -> list[GeminiClient]:
    """The real key with the configured model, then the fallback models (as the app does)."""
    env = dotenv_values(REPO_ROOT / ".env")
    key = env.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set in .env")
    fallbacks = (env.get("GEMINI_FALLBACK_MODEL") or "gemini-flash-lite-latest").split(",")
    models = dict.fromkeys(m.strip() for m in (os.environ.get("LIVE_GEMINI_MODEL"),
                                               env.get("GEMINI_MODEL") or "gemini-flash-latest", *fallbacks)
                           if m and m.strip())
    return [GeminiClient(key, m, f"gemini:{m}") for m in models]


def test_gemini_reads_and_grounds_the_fixture_label(label_image: Image.Image, label_tokens: list[OcrToken]) -> None:
    clients = gemini()
    image = PreparedImage("img_0", label_image.width, label_image.height, label_image)
    result = asyncio.run(structure([image], ["back"], label_tokens, LLMRouter(clients, LIVE_TIMEOUT_S)))

    panel = align_panel(result.result.value.panels[0], "img_0", TokenIndex(label_tokens), result.citations["img_0"])
    names = " ".join(i.name.lower() for i in panel.ingredients)
    assert "peanut" in names and "milk solids" in names
    verified = sum(1 for i in panel.ingredients if i.evidence[0].status == "verified")
    assert verified >= 0.8 * len(panel.ingredients)
    sodium = next(r for r in panel.nutrition.rows if r.key == "sodium_mg")  # type: ignore[union-attr]
    assert all(v.amount is None for v in sodium.values)


def test_gemini_agent_answers_telugu_question_with_engine_verdict() -> None:
    profiles = fixture_data.profiles()
    extraction = fixture_data.scan_result().extraction
    scan = build_scan_result(extraction, engine_adapter.evaluate(extraction, profiles), "te")
    request = AskRequest(question="Thatha కి ఇది సరిపోతుందా?", lang="te", scan=scan, profiles=profiles)
    answer = asyncio.run(agent.ask(request, LLMRouter(gemini(), LIVE_TIMEOUT_S)))
    assert answer.grounded and answer.lang == "te"
    assert any(t.tool == "get_verdict" for t in answer.tool_calls)
    assert [r.profile_id for r in answer.verdict_refs] == ["p_thatha"]
