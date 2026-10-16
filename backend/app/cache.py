"""Disk cache of merged LabelExtractions keyed by image bytes + panel hints + prompt version + model.

Only the extraction is cached (profiles and verdicts change). Images are never written to disk.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from backend.app.config import get_settings
from shared.contract import LabelExtraction
from shared.engine_interface import TermInterpretation


class CacheExtras(BaseModel):
    """LLM work derived from a cached extraction, so a cache hit needs no LLM call at all.
    Summaries are keyed by summary_key(): language + profile + the verdicts they describe."""
    interpretations: dict[str, TermInterpretation] = {}
    interpreted_terms: list[str] = []           # asked successfully (a term may have no categories)
    summaries: dict[str, str] = {}


def summary_key(lang: str, profile_id: str, fingerprint: object) -> str:
    return hashlib.sha256(f"{lang}|{profile_id}|{fingerprint!r}".encode()).hexdigest()[:24]


def cache_key(images: Sequence[bytes], hints: Sequence[str], prompt_version: str, model: str) -> str:
    digest = hashlib.sha256()
    for n, data in enumerate(images):
        hint = hints[n] if n < len(hints) else "unknown"
        digest.update(f"{n}|{hashlib.sha256(data).hexdigest()}|{hint}\n".encode())
    digest.update(f"{prompt_version}|{model}".encode())
    return digest.hexdigest()


class ExtractionCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str, suffix: str = "") -> Path:
        return self.directory / f"{key}{suffix}.json"

    def _write(self, path: Path, text: str) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp, path)
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get(self, key: str) -> LabelExtraction | None:
        try:
            return LabelExtraction.model_validate_json(self._path(key).read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return None

    def put(self, key: str, extraction: LabelExtraction) -> None:
        self._write(self._path(key), extraction.model_dump_json())

    def get_extras(self, key: str) -> CacheExtras:
        try:
            return CacheExtras.model_validate_json(self._path(key, ".extras").read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return CacheExtras()

    def put_extras(self, key: str, extras: CacheExtras) -> None:
        if self._path(key).exists():            # extras only make sense next to a cached extraction
            self._write(self._path(key, ".extras"), extras.model_dump_json())


@lru_cache(maxsize=1)
def get_cache() -> ExtractionCache:
    return ExtractionCache(get_settings().cache_dir / "extractions")
