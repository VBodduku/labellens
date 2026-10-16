from __future__ import annotations

from pathlib import Path

from backend.app import fixtures
from backend.app.cache import ExtractionCache, cache_key


def test_key_depends_on_bytes_order_hints_prompt_and_model() -> None:
    base = cache_key([b"a", b"b"], ["front", "back"], "v1", "m")
    assert base == cache_key([b"a", b"b"], ["front", "back"], "v1", "m")
    assert len({
        base,
        cache_key([b"b", b"a"], ["front", "back"], "v1", "m"),
        cache_key([b"a", b"b"], ["back", "front"], "v1", "m"),
        cache_key([b"a", b"b"], ["front", "back"], "v2", "m"),
        cache_key([b"a", b"b"], ["front", "back"], "v1", "other"),
        cache_key([b"a", b"c"], ["front", "back"], "v1", "m"),
    }) == 6


def test_round_trip_and_misses(tmp_path: Path) -> None:
    cache = ExtractionCache(tmp_path / "x")
    extraction = fixtures.scan_result().extraction
    assert cache.get("missing") is None
    cache.put("k", extraction)
    assert cache.get("k") == extraction
    assert [p.suffix for p in (tmp_path / "x").iterdir()] == [".json"]


def test_corrupt_entry_is_a_miss(tmp_path: Path) -> None:
    cache = ExtractionCache(tmp_path)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert cache.get("bad") is None
