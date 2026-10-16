"""Time evaluate() on the largest saved real extraction, or an explicitly requested fixture."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
from statistics import median
from time import perf_counter_ns

from engine import evaluate
from engine.eval.replay import load_profiles
from engine.eval.reporting import timestamp
from engine.eval.run_eval import HERE, Truth, case_files
from shared.contract import Ingredient, LabelExtraction, Profile, ScanResult


def ingredient_size(items: list[Ingredient]) -> tuple[int, int]:
    count = chars = 0
    pending = list(items)
    while pending:
        item = pending.pop()
        count += 1
        chars += len(item.name)
        pending.extend(item.sub_ingredients)
    return count, chars


def largest_real(dataset: Path, responses: Path) -> LabelExtraction:
    extractions: list[LabelExtraction] = []
    for path in case_files(dataset):
        truth = Truth.model_validate_json(path.read_text(encoding="utf-8"))
        if truth.source != "real":
            continue
        scan = ScanResult.model_validate_json(
            (responses / f"{path.parent.name}.json").read_text(encoding="utf-8")
        )
        if scan.extraction.meta.provider == "fixture":
            raise ValueError(
                f"{path.parent.name}: fixture extraction cannot benchmark a real label"
            )
        extractions.append(scan.extraction)
    if not extractions:
        raise ValueError(
            "No saved real extractions available; real-label performance is unmeasured"
        )
    return max(extractions, key=lambda item: ingredient_size(item.ingredients)[1])


def measure(
    extraction: LabelExtraction,
    profiles: list[Profile],
    *,
    kind: str,
    samples: int = 300,
    warmups: int = 10,
) -> dict[str, object]:
    if samples < 1 or warmups < 0:
        raise ValueError("Samples must be positive and warmups nonnegative")
    for _ in range(warmups):
        evaluate(extraction, profiles)
    times = []
    for _ in range(samples):
        start = perf_counter_ns()
        evaluate(extraction, profiles)
        times.append((perf_counter_ns() - start) / 1e6)
    times.sort()
    p95 = times[math.ceil(0.95 * samples) - 1]
    count, chars = ingredient_size(extraction.ingredients)
    return dict(
        measurement_kind=kind,
        scan_id=extraction.scan_id,
        ingredient_nodes=count,
        ingredient_characters=chars,
        profiles=len(profiles),
        restrictions=sum(len(p.restrictions) for p in profiles),
        samples=samples,
        warmups=warmups,
        median_ms=round(median(times), 4),
        p95_ms=round(p95, 4),
        max_ms=round(times[-1], 4),
        target_ms=50,
        real_target_met=p95 < 50 if kind == "real" else None,
        generated_at=timestamp(datetime.now(timezone.utc)),
        python=platform.python_version(),
        platform=platform.platform(),
        method="Warm in-process evaluate only; excludes import, parsing, HTTP, OCR and model time. Largest means most ingredient-name characters including nested items; target uses p95.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=HERE / "dataset")
    parser.add_argument("--responses", type=Path, default=HERE / "responses")
    parser.add_argument("--profiles", type=Path, default=HERE / "eval_profiles.json")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Explicit software timing only; cannot satisfy the real-label target",
    )
    parser.add_argument("--samples", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        extraction = (
            ScanResult.model_validate_json(
                (HERE.parent.parent / "shared/fixtures/scan_result.json").read_text(
                    encoding="utf-8"
                )
            ).extraction
            if args.fixture
            else largest_real(args.dataset, args.responses)
        )
        result = measure(
            extraction,
            load_profiles(args.profiles),
            kind="fixture" if args.fixture else "real",
            samples=args.samples,
        )
        serialized = json.dumps(result, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
    except (ValueError, OSError) as error:
        parser.exit(2, f"Benchmark failed: {error}\n")


if __name__ == "__main__":
    main()
