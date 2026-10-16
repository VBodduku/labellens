"""Opt-in: real Gemini on the rendered fixture label. Run with `python -m pytest backend/tests -m live`."""
from __future__ import annotations

import asyncio

import pytest
from dotenv import dotenv_values
from PIL import Image

from backend.app.config import REPO_ROOT
from backend.app.llm.gemini import GeminiClient
from backend.app.llm.router import LLMRouter
from backend.app.pipeline.align import TokenIndex, align_panel
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.structure import structure
from shared.contract import OcrToken

pytestmark = pytest.mark.live
LIVE_TIMEOUT_S = 60


def test_gemini_reads_and_grounds_the_fixture_label(label_image: Image.Image, label_tokens: list[OcrToken]) -> None:
    env = dotenv_values(REPO_ROOT / ".env")
    key = env.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set in .env")
    client = GeminiClient(key, env.get("GEMINI_MODEL") or "gemini-flash-latest")
    image = PreparedImage("img_0", label_image.width, label_image.height, label_image)
    result = asyncio.run(structure([image], ["back"], label_tokens, LLMRouter([client], LIVE_TIMEOUT_S)))

    panel = align_panel(result.value.panels[0], "img_0", TokenIndex(label_tokens))
    names = " ".join(i.name.lower() for i in panel.ingredients)
    assert "peanut" in names and "milk solids" in names
    verified = sum(1 for i in panel.ingredients if i.evidence[0].status == "verified")
    assert verified >= 0.8 * len(panel.ingredients)
    sodium = next(r for r in panel.nutrition.rows if r.key == "sodium_mg")  # type: ignore[union-attr]
    assert all(v.amount is None for v in sodium.values)
