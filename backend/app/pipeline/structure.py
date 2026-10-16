"""Build the structuring prompt (photos + compact OCR token list) and call the LLM router."""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from backend.app.llm.base import LLMImage, ProviderName
from backend.app.llm.router import LLMResult, LLMRouter
from backend.app.pipeline.images import PreparedImage
from backend.app.pipeline.llm_schema import LLMExtraction
from shared.contract import OcrToken, PanelHint

PROMPT_VERSION = "structure-v1"
PROMPT_PATH = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "structure.md"
TOKEN_CAP: dict[ProviderName, int] = {"gemini": 1500, "ollama": 600}
LOW_CONFIDENCE = 0.3
JPEG_QUALITY = 85


@lru_cache(maxsize=1)
def prompt_template() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def cap_tokens(tokens: list[OcrToken], cap: int) -> list[OcrToken]:
    """Keep at most `cap` tokens: drop low-confidence ones first, then the least confident; keep order."""
    if len(tokens) <= cap:
        return tokens
    ranked = sorted(range(len(tokens)), key=lambda i: (tokens[i].confidence < LOW_CONFIDENCE, -tokens[i].confidence))
    keep = set(ranked[:cap])
    return [t for i, t in enumerate(tokens) if i in keep]


def format_tokens(tokens: list[OcrToken], image_ids: list[str], cap: int) -> str:
    kept = cap_tokens(tokens, cap)
    blocks: list[str] = []
    for image_id in image_ids:
        lines = [f"{t.token_id}|{t.text}" for t in kept if t.image_id == image_id]
        blocks.append(f"## {image_id}\n" + ("\n".join(lines) if lines else "(no OCR text)"))
    return "\n\n".join(blocks)


def build_prompt(images: list[PreparedImage], hints: list[PanelHint], tokens: list[OcrToken], cap: int) -> str:
    ids = [i.image_id for i in images]
    image_list = "\n".join(
        f"- {image_id}: {hints[n] if n < len(hints) else 'unknown'} panel" for n, image_id in enumerate(ids)
    )
    return (prompt_template()
            .replace("{image_count}", str(len(ids)))
            .replace("{image_list}", image_list)
            .replace("{token_list}", format_tokens(tokens, ids, cap)))


def llm_image(image: PreparedImage) -> LLMImage:
    buffer = io.BytesIO()
    image.for_llm().save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return LLMImage(mime_type="image/jpeg", data=buffer.getvalue())


async def structure(
    images: list[PreparedImage], hints: list[PanelHint], tokens: list[OcrToken], router: LLMRouter,
) -> LLMResult[LLMExtraction]:
    return await router.generate(
        lambda provider: build_prompt(images, hints, tokens, TOKEN_CAP[provider]),
        [llm_image(i) for i in images],
        LLMExtraction,
    )
