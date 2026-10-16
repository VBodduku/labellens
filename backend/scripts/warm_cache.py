"""Scan the demo packets once so the live demo is instant and uses no LLM quota, then prove it.

Pass 1 scans every packet folder in each language (fills the extraction, interpretation and
summary cache). Pass 2 scans again and reports how fast the cache hit was (target < 1.5 s).
Usage (repo root, backend running): python -m backend.scripts.warm_cache <photos_dir> [--url ...] [--lang en te hi]
"""
from __future__ import annotations

import argparse
from pathlib import Path

import httpx

from backend.scripts.smoke_scan import TIMEOUT_S, packets, scan

HIT_TARGET_S = 1.5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("photos_dir", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--lang", nargs="+", default=["en", "te", "hi"], choices=["en", "te", "hi"])
    args = parser.parse_args()
    url = args.url.rstrip("/")

    print("| packet | lang | provider | first s | hit s | cache hit | ok |")
    print("|---|---|---|---|---|---|---|")
    failures = 0
    with httpx.Client(timeout=TIMEOUT_S) as client:
        for name, photos in packets(args.photos_dir):
            for lang in args.lang:
                first_s, first = scan(client, url, photos, lang)
                if isinstance(first, str):
                    print(f"| {name} | {lang} | {first} | {first_s:.1f} | - | - | no |")
                    failures += 1
                    continue
                provider = first.extraction.meta.provider
                if provider == "ocr_only":
                    print(f"| {name} | {lang} | ocr_only | {first_s:.1f} | - | not cached (no LLM) | no |")
                    failures += 1
                    continue
                hit_s, hit = scan(client, url, photos, lang)
                cached = not isinstance(hit, str) and hit.extraction.meta.cache_hit
                ok = cached and hit_s < HIT_TARGET_S
                failures += not ok
                print(f"| {name} | {lang} | {provider} | {first_s:.1f} | {hit_s:.2f} | {'yes' if cached else 'no'} | "
                      f"{'yes' if ok else 'no'} |")
    print(f"\n{'all packets warm' if not failures else f'{failures} packet/language pairs not warm'}"
          f" (target: cache hit under {HIT_TARGET_S} s)")


if __name__ == "__main__":
    main()
