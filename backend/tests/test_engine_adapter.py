from __future__ import annotations

import sys
import types

import pytest

from backend.app import engine_adapter, fixtures
from backend.app.config import get_settings
from shared.contract import Profile


def test_stub_mode_evaluates_fixture_extraction() -> None:
    scan = fixtures.scan_result()
    profiles = [Profile.model_validate(p) for p in _fixture_profiles()]
    output = engine_adapter.evaluate(scan.extraction, profiles)
    assert engine_adapter.engine_mode() == "stub"
    assert [r.profile_id for r in output.reports] == [p.profile_id for p in profiles]
    assert engine_adapter.category_vocabulary()
    assert engine_adapter.explain_term("whey") is None


def test_real_mode_reports_missing_engine_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE_MODE", "real")
    get_settings.cache_clear()
    monkeypatch.setitem(sys.modules, "engine", types.ModuleType("engine"))
    with pytest.raises(RuntimeError, match="evaluate"):
        engine_adapter.restriction_catalog()


def test_real_mode_uses_engine_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE_MODE", "real")
    get_settings.cache_clear()
    fake = types.ModuleType("engine")
    for name in engine_adapter.ENGINE_FUNCTIONS:
        setattr(fake, name, lambda *args, **kwargs: [])
    monkeypatch.setitem(sys.modules, "engine", fake)
    assert engine_adapter.restriction_catalog() == []


def test_invalid_engine_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENGINE_MODE", "fancy")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="ENGINE_MODE"):
        get_settings()


def _fixture_profiles() -> list[dict[str, object]]:
    import json

    return json.loads((fixtures.FIXTURES_DIR / "profiles.json").read_text(encoding="utf-8"))
