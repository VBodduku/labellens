"""Contract-validated copies of shared/fixtures for tests."""
from __future__ import annotations

import json
from functools import lru_cache

from backend.app.config import REPO_ROOT
from shared.contract import Profile, ScanResult

FIXTURES_DIR = REPO_ROOT / "shared" / "fixtures"


@lru_cache(maxsize=1)
def _scan_result() -> ScanResult:
    return ScanResult.model_validate_json((FIXTURES_DIR / "scan_result.json").read_text(encoding="utf-8"))


def scan_result() -> ScanResult:
    return _scan_result().model_copy(deep=True)


def profiles_json() -> list[dict]:
    return json.loads((FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))


def profiles() -> list[Profile]:
    return [Profile.model_validate(p) for p in profiles_json()]
