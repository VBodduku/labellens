"""Settings read once from the environment (and the repo-root .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]

EngineMode = Literal["stub", "real"]


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_api_key_backup: str
    gemini_model: str
    ollama_base_url: str
    ollama_model: str
    ollama_text_model: str
    llm_timeout_s: float
    engine_mode: EngineMode
    cors_origins: tuple[str, ...]
    cache_dir: Path
    max_images: int
    max_image_mb: float
    log_level: str

    @property
    def max_image_bytes(self) -> int:
        return int(self.max_image_mb * 1024 * 1024)

    @property
    def max_scan_body_bytes(self) -> int:
        return self.max_images * self.max_image_bytes + 1024 * 1024


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default).strip()


def _engine_mode(value: str) -> EngineMode:
    if value == "stub":
        return "stub"
    if value == "real":
        return "real"
    raise ValueError(f"ENGINE_MODE must be 'stub' or 'real', got {value!r}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(REPO_ROOT / ".env", override=False)
    cache_dir = Path(_env("CACHE_DIR", ".cache"))
    return Settings(
        gemini_api_key=_env("GEMINI_API_KEY", ""),
        gemini_api_key_backup=_env("GEMINI_API_KEY_BACKUP", ""),
        gemini_model=_env("GEMINI_MODEL", "gemini-flash-latest"),
        ollama_base_url=_env("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=_env("OLLAMA_MODEL", "gemma3:4b"),
        ollama_text_model=_env("OLLAMA_TEXT_MODEL", "gemma3:4b"),
        llm_timeout_s=float(_env("LLM_TIMEOUT_S", "30")),
        engine_mode=_engine_mode(_env("ENGINE_MODE", "stub")),
        cors_origins=tuple(o.strip() for o in _env("CORS_ORIGINS", "").split(",") if o.strip()),
        cache_dir=cache_dir if cache_dir.is_absolute() else REPO_ROOT / cache_dir,
        max_images=int(_env("MAX_IMAGES", "3")),
        max_image_mb=float(_env("MAX_IMAGE_MB", "8")),
        log_level=_env("LOG_LEVEL", "info").upper(),
    )
