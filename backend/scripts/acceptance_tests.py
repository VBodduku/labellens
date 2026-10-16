"""Run the three acceptance tests against a running backend and save the evidence (docs/TEST_RESULTS.md).

Test 1 sends a clear label photo; Test 2 the same photo with the ingredient list and the sodium value blurred;
Test 3 the same photo with the lower half of the nutrition table covered (an incomplete panel). Each result
is checked against the states the photo justifies, and a trimmed copy of the response (verdicts with their
evidence, couldn't-read items, contradictions) is written as JSON. Photos are not committed: pass the folder.

Usage (repo root): python -m backend.scripts.acceptance_tests "<photos dir>" [--url http://localhost:8000]
                   [--photo img_5.jpeg] [--out docs/test_evidence]
"""
from __future__ import annotations

import argparse
import io
import json
import time
from collections.abc import Callable
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFilter

from shared.contract import Profile, ScanResult

TIMEOUT_S = 90.0
Box = tuple[int, int, int, int]
# Regions on the Bingo back label (img_5.jpeg, 1080 x 1276 px), read off the photo.
INGREDIENT_LIST: Box = (60, 140, 530, 397)
SODIUM_VALUES: Box = (740, 553, 1015, 583)
LOWER_NUTRITION: Box = (556, 410, 1016, 616)
PANEL_COLOUR = (113, 62, 175)

PROFILES = [
    Profile.model_validate(p) for p in (
        {"profile_id": "p_asha", "name": "Asha", "restrictions": [
            {"id": "r_asha_milk", "kind": "allergy", "key": "milk", "label": "Milk allergy", "severity": "strict"},
            {"id": "r_asha_peanut", "kind": "allergy", "key": "peanut", "label": "Peanut allergy", "severity": "strict"}]},
        {"profile_id": "p_ravi", "name": "Ravi", "restrictions": [
            {"id": "r_ravi_jain", "kind": "diet", "key": "jain", "label": "Jain", "severity": "strict"},
            {"id": "r_ravi_veg", "kind": "diet", "key": "vegetarian", "label": "Vegetarian", "severity": "strict"}]},
        {"profile_id": "p_dadi", "name": "Dadi", "restrictions": [
            {"id": "r_dadi_sugar", "kind": "health_limit", "key": "diabetes_sugar", "label": "Diabetic: limit sugar",
             "severity": "strict", "threshold": {"nutrient": "total_sugars_g", "max_value": 22.5, "basis": "per_100g"}},
            {"id": "r_dadi_sodium", "kind": "health_limit", "key": "low_sodium", "label": "Low sodium",
             "severity": "strict", "threshold": {"nutrient": "sodium_mg", "max_value": 600, "basis": "per_100g"}}]},
    )
]

# Allowed states per restriction (the first is what the photo shows; others are acceptable honest answers).
EXPECTED: dict[str, dict[str, tuple[str, ...]]] = {
    "test1_clear": {
        "r_asha_milk": ("conflict",), "r_asha_peanut": ("not_listed", "unknown"),
        "r_ravi_jain": ("conflict",), "r_ravi_veg": ("possible",),
        "r_dadi_sugar": ("possible",), "r_dadi_sodium": ("conflict",),
    },
    "test2_blurred": {
        "r_asha_milk": ("conflict",),               # "CONTAINS MILK" stays readable below the blur
        "r_asha_peanut": ("unknown",),              # never "not listed" from a list it could not read
        "r_ravi_jain": ("unknown", "conflict"),     # onion/garlic are under the blur
        "r_ravi_veg": ("unknown", "possible"),
        "r_dadi_sugar": ("not_listed", "possible", "unknown"),   # the sugar row is readable and decides the limit
        "r_dadi_sodium": ("unknown",),              # value blurred: can't determine, never "within limit"
    },
    "test3_incomplete_panel": {
        "r_asha_milk": ("conflict",), "r_asha_peanut": ("not_listed", "unknown"),
        "r_ravi_jain": ("conflict",), "r_ravi_veg": ("possible",),
        "r_dadi_sugar": ("possible",),              # sugar rows are above the cover
        "r_dadi_sodium": ("unknown",),              # sodium row covered: must not be invented
    },
}


def blurred(image: Image.Image, *boxes: Box) -> Image.Image:
    out = image.copy()
    for box in boxes:
        out.paste(out.crop(box).filter(ImageFilter.GaussianBlur(9)), box[:2])
    return out


def covered(image: Image.Image, box: Box) -> Image.Image:
    out = image.copy()
    ImageDraw.Draw(out).rectangle(box, fill=PANEL_COLOUR)
    return out


VARIANTS: dict[str, Callable[[Image.Image], Image.Image]] = {
    "test1_clear": lambda image: image,
    "test2_blurred": lambda image: blurred(image, INGREDIENT_LIST, SODIUM_VALUES),
    "test3_incomplete_panel": lambda image: covered(image, LOWER_NUTRITION),
}


def jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def evidence_of(result: ScanResult, seconds: float) -> dict[str, object]:
    """What a reviewer needs to judge the test, without OCR tokens or photo bytes."""
    extraction = result.extraction
    labels = {r.id: r.label for p in PROFILES for r in p.restrictions}
    return {
        "provider": extraction.meta.provider, "model": extraction.meta.model, "seconds": round(seconds, 1),
        "retries": [r.model_dump() for r in extraction.meta.retries],
        "ingredients": [{"text": i.raw_text, "readability": i.readability} for i in extraction.ingredients],
        "ingredients_section": extraction.ingredients_section.model_dump(include={"presence", "complete", "issues"}),
        "allergen_statements": [{"type": s.type, "text": s.raw_text} for s in extraction.allergen_statements],
        "nutrition": [{"row": r.raw_label, "values": [{"basis": v.basis, "amount": v.amount, "printed": v.raw_text,
                                                       "readability": v.readability} for v in r.values]}
                      for r in (extraction.nutrition.rows if extraction.nutrition else [])],
        "verdicts": [{
            "profile": report.profile_id, "restriction": labels.get(r.restriction_id, r.restriction_id),
            "restriction_id": r.restriction_id, "state": r.state, "unknown_kind": r.unknown_kind,
            "reason": r.reason_code, "explanation": r.explanation,
            "evidence": [{"text": e.text, "status": e.status, "located": e.box is not None} for e in r.evidence],
        } for report in result.reports for r in report.results],
        "couldnt_read": [{"message_key": u.message_key, "detail": u.detail, "retake_region": u.region is not None}
                         for u in result.unknowns],
        "contradictions": [{"kind": c.kind, "explanation": c.explanation} for c in result.contradictions],
    }


def run(name: str, photo: bytes, url: str) -> tuple[dict[str, object], list[str]]:
    started = time.perf_counter()
    response = httpx.post(f"{url}/api/scan", timeout=TIMEOUT_S, files=[("images", (f"{name}.jpg", photo, "image/jpeg"))],
                          data={"profiles": json.dumps([p.model_dump() for p in PROFILES]), "lang": "en"})
    response.raise_for_status()
    evidence = evidence_of(ScanResult.model_validate(response.json()), time.perf_counter() - started)
    failures = [
        f"{v['restriction_id']}: expected {'/'.join(EXPECTED[name][v['restriction_id']])}, got {v['state']}"
        for v in evidence["verdicts"]  # type: ignore[union-attr]
        if v["state"] not in EXPECTED[name][v["restriction_id"]]
    ]
    flagged = [v for v in evidence["verdicts"] if v["state"] in ("conflict", "possible")]  # type: ignore[union-attr]
    failures += [f"{v['restriction_id']}: flagged without evidence" for v in flagged if not v["evidence"]]
    return evidence, failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("photos", type=Path)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--photo", default="img_5.jpeg")
    parser.add_argument("--out", type=Path, default=Path("docs/test_evidence"))
    args = parser.parse_args()
    image = Image.open(args.photos / args.photo)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, variant in VARIANTS.items():
        evidence, failures = run(name, jpeg(variant(image)), args.url.rstrip("/"))
        (args.out / f"{name}.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
        print(f"{name}: {'PASS' if not failures else 'FAIL'} ({evidence['provider']}, {evidence['seconds']} s)")
        for failure in failures:
            print(f"  - {failure}")


if __name__ == "__main__":
    main()
