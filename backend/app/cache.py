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

from pydantic import ValidationError

from backend.app.config import get_settings
from shared.contract import LabelExtraction


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

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> LabelExtraction | None:
        path = self._path(key)
        try:
            return LabelExtraction.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            return None

    def put(self, key: str, extraction: LabelExtraction) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(extraction.model_dump_json())
            os.replace(tmp, self._path(key))
        except OSError:
            Path(tmp).unlink(missing_ok=True)
            raise


@lru_cache(maxsize=1)
def get_cache() -> ExtractionCache:
    return ExtractionCache(get_settings().cache_dir / "extractions")
