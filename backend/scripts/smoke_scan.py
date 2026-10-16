"""POST every packet folder in a directory to a running backend and print a summary table.

Each subfolder is one packet with 1-3 photos (sent in file-name order). Uses the fixture family
(peanut + tree-nut allergy, diabetic + low sodium, Jain + sesame). "overall" is each profile's
overall state, "states" every result state seen (C conflict, P possible, N not listed, U unknown).
Usage (repo root): python -m backend.scripts.smoke_scan <photos_dir> [--url http://localhost:8000] [--lang en]
"""
from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import httpx

from backend.app.config import REPO_ROOT
from shared.contract import Ingredient, ScanResult

PROFILES = REPO_ROOT / "shared" / "fixtures" / "profiles.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
        ".heic": "image/heic", ".heif": "image/heif"}
TIMEOUT_S = 60.0
COLUMNS = ("packet", "provider", "secs", "ingr", "verified", "ingr_ok", "nutr_ok", "allg_ok", "veg", "cache",
           "retries", "overall", "states")
STATE_SHORT = {"conflict": "C", "possible": "P", "not_listed": "N", "unknown": "U"}


def flatten(items: list[Ingredient]) -> list[Ingredient]:
    return [x for i in items for x in (i, *flatten(i.sub_ingredients))]


def packets(root: Path) -> list[tuple[str, list[Path]]]:
    found = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        photos = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)[:3]
        if photos:
            found.append((folder.name, photos))
    return found


def scan(client: httpx.Client, url: str, photos: list[Path], lang: str) -> tuple[float, ScanResult | str]:
    files = [("images", (p.name, p.read_bytes(), MIME[p.suffix.lower()])) for p in photos]
    started = time.perf_counter()
    try:
        response = client.post(f"{url}/api/scan", files=files,
                               data={"profiles": PROFILES.read_text(encoding="utf-8"), "lang": lang})
    except httpx.HTTPError as exc:
        return time.perf_counter() - started, f"error: {type(exc).__name__}"
    elapsed = time.perf_counter() - started
    if response.status_code != 200:
        return elapsed, f"HTTP {response.status_code}: {response.json().get('error_code', '?')}"
    return elapsed, ScanResult.model_validate(response.json())


def row(name: str, elapsed: float, result: ScanResult) -> tuple[tuple[str, ...], int, int]:
    e = result.extraction
    items = flatten(e.ingredients)
    verified = sum(1 for i in items if any(ev.status == "verified" for ev in i.evidence))
    pct = f"{100 * verified / len(items):.0f}%" if items else "-"
    yes = {True: "yes", False: "no"}
    overall = "/".join(STATE_SHORT[r.overall] for r in result.reports)
    states = "".join(sorted({STATE_SHORT[x.state] for r in result.reports for x in r.results}))
    retries = ",".join(r.outcome for r in e.meta.retries) or "-"
    cells = (name, e.meta.provider, f"{elapsed:.1f}", str(len(items)), pct, yes[e.ingredients_section.complete],
             yes[e.nutrition_section.complete], yes[e.allergen_section.complete], e.veg_mark.value,
             yes[e.meta.cache_hit], retries, overall, states)
    return cells, verified, len(items)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos_dir", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--lang", default="en")
    args = parser.parse_args()

    rows: list[tuple[str, ...]] = []
    durations: list[float] = []
    seen_states: set[str] = set()
    verified_total = items_total = 0
    with httpx.Client(timeout=TIMEOUT_S) as client:
        for name, photos in packets(args.photos_dir):
            elapsed, result = scan(client, args.url.rstrip("/"), photos, args.lang)
            durations.append(elapsed)
            if isinstance(result, str):
                rows.append((name, result, f"{elapsed:.1f}", *("-",) * (len(COLUMNS) - 3)))
                continue
            cells, verified, items = row(name, elapsed, result)
            rows.append(cells)
            seen_states.update(cells[-1])
            verified_total += verified
            items_total += items

    widths = [max(len(c), *(len(r[i]) for r in rows)) for i, c in enumerate(COLUMNS)] if rows else []
    print("| " + " | ".join(c.ljust(w) for c, w in zip(COLUMNS, widths)) + " |")
    print("|" + "|".join("-" * (w + 2) for w in widths) + "|")
    for r in rows:
        print("| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |")
    if durations:
        overall = f"{100 * verified_total / items_total:.0f}%" if items_total else "-"
        print(f"\npackets: {len(rows)}  p50: {statistics.median(durations):.1f} s  "
              f"ingredients verified: {overall} ({verified_total}/{items_total})")
        missing = [s for s in "CPNU" if s not in seen_states]
        print("states seen across packets (C=conflict P=possible N=not_listed U=unknown): "
              f"{''.join(sorted(seen_states)) or '-'}" + (f"  missing: {''.join(missing)}" if missing else "  (all four)"))


if __name__ == "__main__":
    main()
