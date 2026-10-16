"""Record one real structuring response for the offline FakeLLM tests.

Renders the fixture test label, runs OCR, sends the real prompt to one provider and saves the
validated JSON to backend/tests/data/<provider>_test_label.json.
Usage (repo root): python -m backend.scripts.record_fake_llm [gemini|ollama]
"""
from __future__ import annotations

import asyncio
import sys
import time

from backend.app.config import REPO_ROOT, get_settings
from backend.app.llm.base import LLMClient
from backend.app.llm.ollama import OllamaClient
from backend.app.llm.router import LLMRouter, gemini_clients
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.ocr import ocr_image
from backend.app.pipeline.structure import structure
from backend.scripts.make_test_label import fixture_tokens, render_label

DATA_DIR = REPO_ROOT / "backend" / "tests" / "data"
RECORD_TIMEOUT_S = 180.0


def clients_for(provider: str) -> list[LLMClient]:
    settings = get_settings()
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise SystemExit("GEMINI_API_KEY is not set in .env")
        return gemini_clients()
    if provider == "ollama":
        return [OllamaClient(settings.ollama_base_url, settings.ollama_model)]
    raise SystemExit("provider must be gemini or ollama")


async def record(provider: str) -> None:
    tokens, size = fixture_tokens()
    label = render_label(tokens, size)
    image = PreparedImage("img_0", label.width, label.height, label)
    ocr_tokens = ocr_image(label, "img_0")
    router = LLMRouter(clients_for(provider), RECORD_TIMEOUT_S)
    started = time.perf_counter()
    result = await structure([image], ["back"], ocr_tokens, router)
    out = DATA_DIR / f"{provider}_test_label.json"
    out.write_text(result.value.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"{result.provider}/{result.model}: {time.perf_counter() - started:.1f} s, "
          f"{result.attempts} attempt(s) -> {out}")


if __name__ == "__main__":
    asyncio.run(record(sys.argv[1] if len(sys.argv) > 1 else "gemini"))
