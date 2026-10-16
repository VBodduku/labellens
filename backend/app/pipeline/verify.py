"""Self-verification loop (spec §4.6): find likely misreads, re-read only that region, log every attempt.

Triggers, checked in order (each reason is tried at most once, at most MAX_ROUNDS re-reads):
  1. nutrition consistency check is inconsistent or lists suspect values
  2. ingredients incomplete: truncated at the photo edge (cannot be fixed -> ask for a retake),
     or containing unreadable spans
  3. a nutrient that a profile threshold needs has no readable value
  4. more than 30 % of evidence is unverified
Re-read = crop (padded 8 %), upscale x2, CLAHE, re-OCR, focused LLM re-read of that section only.
A re-read is accepted only if it is measurably better. Whatever still triggers afterwards is
unresolved: pending_unknowns() turns it into UnknownItems with the region, so the UI can offer
"retake this area" (also for cache hits and rechecks, where no re-read runs).
"""
from __future__ import annotations

import io
import logging
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from backend.app import engine_adapter
from backend.app.llm.base import LLMImage
from backend.app.llm.router import AllProvidersFailedError, LLMRouter
from backend.app.pipeline.align import PanelExtraction, TokenIndex, align_panel, union_box
from backend.app.pipeline.images import OCR_MAX_SIDE, PreparedImage
from backend.app.pipeline.llm_schema import LLMExtraction
from backend.app.pipeline.merge import assign_ingredient_ids
from backend.app.pipeline.ocr import ocr_image_async
from backend.app.pipeline.structure import JPEG_QUALITY, TOKEN_CAP, build_prompt
from shared.contract import (
    Box,
    Evidence,
    Ingredient,
    LabelExtraction,
    NutrientRow,
    NutritionTable,
    OcrToken,
    Profile,
    RetryRecord,
    UnknownItem,
)

logger = logging.getLogger("labellens.verify")

MAX_ROUNDS = 2
BUDGET_S = 25.0
MIN_ROUND_S = 4.0
PAD = 0.08
UPSCALE = 2.0
UNVERIFIED_MAX = 0.30
REREAD_PROMPT = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "reread_region.md"
FULL_IMAGE = Box(x=0, y=0, w=1, h=1)

Section = Literal["ingredients", "nutrition"]


@dataclass(frozen=True)
class Trigger:
    reason: str
    section: Section
    image_id: str
    box: Box
    focus: str
    reread: bool = True


# ------------------------------------------------------------------------------------------------
# Triggers
# ------------------------------------------------------------------------------------------------
def _boxes(evidence: Sequence[Evidence | None]) -> list[tuple[str, Box]]:
    return [(e.image_id, e.box) for e in evidence if e is not None and e.box is not None]


def _region(evidence: Sequence[Evidence | None], fallback_image: str) -> tuple[str, Box]:
    located = _boxes(evidence)
    if not located:
        return fallback_image, FULL_IMAGE
    image_id = Counter(i for i, _ in located).most_common(1)[0][0]
    return image_id, union_box([b for i, b in located if i == image_id])


def _value_evidence(nutrition: NutritionTable | None, keys: set[str] | None = None) -> list[Evidence | None]:
    if nutrition is None:
        return []
    return [v.evidence for r in nutrition.rows if keys is None or r.key in keys for v in r.values]


def _ingredient_evidence(extraction: LabelExtraction) -> list[Evidence]:
    def walk(items: Sequence[Ingredient]) -> list[Evidence]:
        return [e for i in items for e in (*i.evidence, *walk(i.sub_ingredients))]
    return walk(extraction.ingredients)


def needed_nutrients(profiles: Sequence[Profile]) -> list[str]:
    catalog = {c.key: c for c in engine_adapter.restriction_catalog()}
    keys: list[str] = []
    for profile in profiles:
        for restriction in profile.restrictions:
            threshold = restriction.threshold
            item = catalog.get(restriction.key)
            if threshold is None and item is not None and item.needs_threshold:
                threshold = item.default_threshold
            if threshold is not None and threshold.nutrient not in keys:
                keys.append(threshold.nutrient)
    return keys


def _readable(nutrition: NutritionTable | None, key: str) -> bool:
    return nutrition is not None and any(
        v.amount is not None for r in nutrition.rows if r.key == key for v in r.values)


def unverified_ratio(extraction: LabelExtraction) -> float:
    evidence = _ingredient_evidence(extraction) + [e for s in extraction.allergen_statements for e in s.evidence]
    evidence += [e for e in _value_evidence(extraction.nutrition) if e is not None]
    return sum(e.status == "unverified" for e in evidence) / len(evidence) if evidence else 0.0


def find_triggers(extraction: LabelExtraction, profiles: Sequence[Profile]) -> list[Trigger]:
    """Every applicable trigger, in spec order."""
    first_image = extraction.images[0].image_id
    triggers: list[Trigger] = []

    analysis = engine_adapter.analyze_nutrition(extraction)
    if analysis is not None and (analysis.consistency.status == "inconsistent" or analysis.consistency.suspect_keys):
        suspects = set(analysis.consistency.suspect_keys)
        image_id, box = _region(_value_evidence(extraction.nutrition, suspects or None), first_image)
        triggers.append(Trigger("nutrition_inconsistent", "nutrition", image_id, box,
                                f"the values of {', '.join(sorted(suspects)) or 'the energy and macronutrients'}"))

    section = extraction.ingredients_section
    if not section.complete and section.presence != "not_found":
        if "truncated_at_image_edge" in section.issues:
            last = extraction.ingredients[-1].evidence if extraction.ingredients else []
            image_id, box = _region(last or _ingredient_evidence(extraction), first_image)
            triggers.append(Trigger("ingredients_truncated", "ingredients", image_id, box, "", reread=False))
        if section.unreadable_regions:
            # Crop the whole ingredients block so an accepted re-read is a complete list, not a fragment.
            image_id, box = _region([*_ingredient_evidence(extraction), *section.unreadable_regions], first_image)
            triggers.append(Trigger("ingredients_unreadable", "ingredients", image_id, box,
                                    "the blurred, glared or partly hidden words"))

    for key in needed_nutrients(profiles):
        if extraction.nutrition_section.presence != "not_found" and not _readable(extraction.nutrition, key):
            evidence = _value_evidence(extraction.nutrition, {key}) or _value_evidence(extraction.nutrition)
            image_id, box = _region(evidence, first_image)
            triggers.append(Trigger(f"nutrition_value_unreadable:{key}", "nutrition", image_id, box,
                                    f"the {key} row"))

    if unverified_ratio(extraction) > UNVERIFIED_MAX:
        image_id, box = _region(_ingredient_evidence(extraction), first_image)
        triggers.append(Trigger("evidence_unverified", "ingredients", image_id, box, "every ingredient"))
    return triggers


# ------------------------------------------------------------------------------------------------
# Region re-read
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Crop:
    image: Image.Image          # enhanced, upscaled crop
    x0: int                     # crop origin and size in the original OCR image's pixels
    y0: int
    width: int
    height: int


def padded_crop(image: PreparedImage, box: Box) -> Crop:
    w, h = image.width, image.height
    pad_x, pad_y = box.w * w * PAD, box.h * h * PAD
    x0 = max(0, int(box.x * w - pad_x))
    y0 = max(0, int(box.y * h - pad_y))
    x1 = min(w, int((box.x + box.w) * w + pad_x) + 1)
    y1 = min(h, int((box.y + box.h) * h + pad_y) + 1)
    region = image.ocr_image.crop((x0, y0, x1, y1))
    scale = min(UPSCALE, OCR_MAX_SIDE / max(region.size))
    if scale > 1:
        region = region.resize((round(region.width * scale), round(region.height * scale)), Image.Resampling.LANCZOS)
    return Crop(enhance(region), x0, y0, x1 - x0, y1 - y0)


def enhance(image: Image.Image) -> Image.Image:
    """CLAHE on the lightness channel: lifts faint or glared print without shifting colours."""
    lab = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lightness)
    return Image.fromarray(cv2.cvtColor(cv2.merge((lightness, a, b)), cv2.COLOR_LAB2RGB))


def map_tokens(tokens: Sequence[OcrToken], crop: Crop, image: PreparedImage, round_no: int) -> list[OcrToken]:
    """Crop-normalised token boxes -> full-image boxes, with ids that cannot collide (img_0:r1t5)."""
    mapped: list[OcrToken] = []
    for n, token in enumerate(tokens):
        b = token.box
        box = Box(
            x=round((crop.x0 + b.x * crop.width) / image.width, 4),
            y=round((crop.y0 + b.y * crop.height) / image.height, 4),
            w=round(b.w * crop.width / image.width, 4),
            h=round(b.h * crop.height / image.height, 4),
        )
        mapped.append(token.model_copy(update={
            "token_id": f"{image.image_id}:r{round_no}t{n}", "image_id": image.image_id, "box": box}))
    return mapped


def reread_prompt(trigger: Trigger, image: PreparedImage, tokens: list[OcrToken], cap: int) -> str:
    fields = ("ingredients, ingredients_section" if trigger.section == "ingredients"
              else "nutrition, nutrition_section")
    focus = (REREAD_PROMPT.read_text(encoding="utf-8")
             .replace("{image_id}", image.image_id).replace("{section}", trigger.section)
             .replace("{problem}", trigger.reason.replace("_", " ")).replace("{fields}", fields)
             .replace("{focus}", trigger.focus))
    return build_prompt([image], ["unknown"], tokens, cap) + focus


def _jpeg(image: Image.Image) -> LLMImage:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return LLMImage(mime_type="image/jpeg", data=buffer.getvalue())


# ------------------------------------------------------------------------------------------------
# Acceptance
# ------------------------------------------------------------------------------------------------
def _readable_count(nutrition: NutritionTable | None) -> int:
    return 0 if nutrition is None else sum(v.amount is not None for r in nutrition.rows for v in r.values)


def merge_rows(current: NutritionTable | None, reread: NutritionTable) -> NutritionTable:
    """Re-read values replace the current ones (same key + basis) when they are readable."""
    rows: dict[tuple[str, str], NutrientRow] = {
        (r.key, r.raw_label if r.key == "other" else ""): r for r in (current.rows if current else [])}
    for row in reread.rows:
        key = (row.key, row.raw_label if row.key == "other" else "")
        existing = rows.get(key)
        if existing is None:
            rows[key] = row
            continue
        values = {v.basis: v for v in existing.values}
        for value in row.values:
            if value.amount is not None or value.basis not in values:
                values[value.basis] = value
        rows[key] = existing.model_copy(update={"values": list(values.values())})
    base = current or reread
    return base.model_copy(update={"rows": list(rows.values())})


def _suspects(extraction: LabelExtraction) -> tuple[bool, int]:
    analysis = engine_adapter.analyze_nutrition(extraction)
    if analysis is None:
        return False, 0
    return analysis.consistency.status == "inconsistent", len(analysis.consistency.suspect_keys)


def candidate(extraction: LabelExtraction, trigger: Trigger, panel: PanelExtraction,
              crop_tokens: list[OcrToken]) -> LabelExtraction | None:
    """The extraction with the re-read section swapped in, or None if the re-read found nothing."""
    tokens = [*extraction.ocr_tokens, *crop_tokens]
    if trigger.section == "nutrition":
        if panel.nutrition is None or not panel.nutrition.rows:
            return None
        nutrition = merge_rows(extraction.nutrition, panel.nutrition)
        issues = [i for i in extraction.nutrition_section.issues if not i.startswith("value_not_on_photo")]
        readable = all(v.amount is not None for r in nutrition.rows for v in r.values)
        section = extraction.nutrition_section.model_copy(update={
            "issues": list(dict.fromkeys([*issues, *panel.nutrition_section.issues])),
            "complete": panel.nutrition_section.complete and readable,
            "unreadable_regions": panel.nutrition_section.unreadable_regions,
        })
        return extraction.model_copy(update={"nutrition": nutrition, "nutrition_section": section, "ocr_tokens": tokens})
    if not panel.ingredients:
        return None
    return extraction.model_copy(update={
        "ingredients": assign_ingredient_ids(panel.ingredients),
        "ingredients_section": panel.ingredients_section,
        "ocr_tokens": tokens,
    })


def _verified_items(extraction: LabelExtraction) -> int:
    return sum(1 for i in extraction.ingredients if any(e.status == "verified" for e in i.evidence))


def is_better(trigger: Trigger, before: LabelExtraction, after: LabelExtraction) -> bool:
    if trigger.reason == "nutrition_inconsistent":
        (was_bad, was_count), (now_bad, now_count) = _suspects(before), _suspects(after)
        return (was_bad and not now_bad) or now_count < was_count
    if trigger.reason.startswith("nutrition_value_unreadable:"):
        key = trigger.reason.split(":", 1)[1]
        return _readable(after.nutrition, key) and not _readable(before.nutrition, key)
    if trigger.reason == "evidence_unverified":
        return unverified_ratio(after) < unverified_ratio(before)
    b, a = before.ingredients_section, after.ingredients_section
    return a.complete or (len(a.unreadable_regions) < len(b.unreadable_regions)
                          and _verified_items(after) >= _verified_items(before))


# ------------------------------------------------------------------------------------------------
# Loop
# ------------------------------------------------------------------------------------------------
def retake_unknown(trigger: Trigger) -> UnknownItem:
    truncated = trigger.reason == "ingredients_truncated"
    return UnknownItem(
        section=trigger.section,
        message_key="unknown.ingredients_truncated" if truncated else "unknown.retake_region",
        detail=trigger.reason,
        region=Evidence(image_id=trigger.image_id, text="", box=trigger.box, status="approximate"),
    )


async def _reread(trigger: Trigger, extraction: LabelExtraction, image: PreparedImage, round_no: int,
                  router: LLMRouter, timeout_s: float) -> tuple[LabelExtraction | None, int]:
    crop = padded_crop(image, trigger.box)
    crop_tokens = map_tokens(await ocr_image_async(crop.image, image.image_id), crop, image, round_no)
    result = await router.generate(
        lambda provider: reread_prompt(trigger, image, crop_tokens, TOKEN_CAP[provider]),
        [_jpeg(crop.image)], LLMExtraction, timeout_s=timeout_s,
    )
    panel = result.value.panels[0]
    aligned = align_panel(panel, image.image_id, TokenIndex([*extraction.ocr_tokens, *crop_tokens]))
    return candidate(extraction, trigger, aligned, crop_tokens), result.attempts


async def verify(
    extraction: LabelExtraction, images: Sequence[PreparedImage], profiles: Sequence[Profile],
    router: LLMRouter, budget_s: float = BUDGET_S,
) -> LabelExtraction:
    if extraction.meta.provider == "ocr_only":
        return extraction
    deadline = time.monotonic() + min(budget_s, BUDGET_S)
    by_id = {i.image_id: i for i in images}
    retries = list(extraction.meta.retries)
    attempts = extraction.meta.attempts
    tried: set[str] = set()
    rounds = 0

    while True:
        trigger = next((t for t in find_triggers(extraction, profiles) if t.reason not in tried), None)
        if trigger is None:
            break
        tried.add(trigger.reason)
        if not trigger.reread:
            retries.append(RetryRecord(reason=trigger.reason, action="ask_user_retake", outcome="unresolved"))
            continue
        remaining = deadline - time.monotonic()
        if rounds >= MAX_ROUNDS or remaining < MIN_ROUND_S:
            outcome = "skipped_budget"
        elif not router.can_generate():
            outcome = "skipped_rate_limit"
        else:
            rounds += 1
            try:
                after, calls = await _reread(trigger, extraction, by_id[trigger.image_id], rounds, router, remaining)
                attempts += calls
                if after is not None and is_better(trigger, extraction, after):
                    extraction, outcome = after, "resolved"
                else:
                    outcome = "unchanged"
            except AllProvidersFailedError as exc:
                outcome = "skipped_rate_limit" if exc.rate_limited else "unchanged"
        retries.append(RetryRecord(reason=trigger.reason, action=f"reread_region:{trigger.image_id}", outcome=outcome))
        logger.info("verify round", extra={"fields": {"reason": trigger.reason, "outcome": outcome}})

    meta = extraction.meta.model_copy(update={"retries": retries, "attempts": attempts})
    return extraction.model_copy(update={"meta": meta})


def pending_unknowns(extraction: LabelExtraction, profiles: Sequence[Profile]) -> list[UnknownItem]:
    """Every trigger that still applies is unresolved: tell the user where to retake."""
    return [retake_unknown(t) for t in find_triggers(extraction, profiles)]


def merge_unknowns(engine: Sequence[UnknownItem], pipeline: Sequence[UnknownItem]) -> list[UnknownItem]:
    """Pipeline unknowns (always with a retake region) win over engine items of the same kind."""
    covered = {(u.section, u.message_key) for u in pipeline}
    return [*pipeline, *(u for u in engine if (u.section, u.message_key) not in covered)]
