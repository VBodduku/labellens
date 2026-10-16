"""Contract-validated copies of shared/fixtures, served until the real pipeline replaces them."""
from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from backend.app.config import REPO_ROOT
from shared.contract import AskResponse, ExplainResponse, ProfileParseResponse, ScanResult

FIXTURES_DIR = REPO_ROOT / "shared" / "fixtures"

M = TypeVar("M", bound=BaseModel)


@lru_cache(maxsize=None)
def _load(name: str, model: type[BaseModel]) -> BaseModel:
    return model.model_validate_json((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def _fresh(name: str, model: type[M]) -> M:
    loaded = _load(name, model)
    assert isinstance(loaded, model)
    return loaded.model_copy(deep=True)


def scan_result() -> ScanResult:
    return _fresh("scan_result.json", ScanResult)


def ask_response() -> AskResponse:
    return _fresh("ask_response.json", AskResponse)


def profile_parse() -> ProfileParseResponse:
    return _fresh("profile_parse.json", ProfileParseResponse)


def explain() -> ExplainResponse:
    return _fresh("explain.json", ExplainResponse)
