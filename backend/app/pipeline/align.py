"""Ground every LLM-extracted item in OCR tokens on the photo (spec §4.4).

For each cited span:
  1. the cited tokens' text matches the item (token_set_ratio >= 85)        -> verified
  2. else the best window of 1-12 consecutive tokens (partial_ratio >= 88)  -> verified
  3. else the model's own box_2d                                            -> approximate
  4. else                                                                   -> unverified, no box
Verified evidence is split into one Evidence per printed line. Numbers (percentages, nutrient
amounts) are taken from the verified OCR text, never from the LLM, when they disagree.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from backend.app.pipeline.llm_schema import (
    Box2d,
    LLMIngredient,
    LLMNutrientRow,
    LLMNutrientValue,
    LLMNutrition,
    LLMPanel,
    LLMSection,
    LLMVegMark,
)
from backend.app.pipeline.textnorm import (
    clean_item_text,
    compact,
    norm,
    numbers_differ,
    parse_number,
    parse_percentage,
)
from shared.contract import (
    AllergenStatement,
    Box,
    Claim,
    Evidence,
    EvidenceStatus,
    Ingredient,
    NutrientRow,
    NutrientValue,
    NutritionTable,
    OcrToken,
    Readability,
    SectionStatus,
    VegMark,
)

CITED_MIN_SCORE = 85
WINDOW_MIN_SCORE = 88
MAX_WINDOW = 12
MIN_WINDOW_LENGTH = 0.8         # window text must be at least this x item text (no "Sugar" in "Invert Sugar")
MAX_LENGTH_FACTOR = 1.5         # matched text may be at most this x item text (+ slack) long
LENGTH_SLACK = 4
CONFIDENCE: dict[EvidenceStatus, float] = {"verified": 1.0, "approximate": 0.7, "unverified": 0.4}
MISMATCH_ISSUE = "llm_ocr_number_mismatch"
NOT_ON_PHOTO_ISSUE = "value_not_on_photo"
NESTED_MIN_SCORE = 90           # a sub-ingredient must appear inside its parent's printed text


class TokenIndex:
    def __init__(self, tokens: Iterable[OcrToken]) -> None:
        self.by_id: dict[str, OcrToken] = {}
        self.by_image: dict[str, list[OcrToken]] = {}
        self.position: dict[str, int] = {}
        for token in tokens:
            image_tokens = self.by_image.setdefault(token.image_id, [])
            self.position[token.token_id] = len(image_tokens)
            image_tokens.append(token)
            self.by_id[token.token_id] = token


@dataclass(frozen=True)
class Alignment:
    status: EvidenceStatus
    evidence: list[Evidence]
    ocr_text: str | None = None     # joined text of the matched tokens (verified only)

    @property
    def confidence(self) -> float:
        return CONFIDENCE[self.status]


def union_box(boxes: Sequence[Box]) -> Box:
    x0, y0 = min(b.x for b in boxes), min(b.y for b in boxes)
    x1, y1 = max(b.x + b.w for b in boxes), max(b.y + b.h for b in boxes)
    return Box(x=round(x0, 4), y=round(y0, 4), w=round(min(1.0, x1) - x0, 4), h=round(min(1.0, y1) - y0, 4))


def _same_line(a: OcrToken, b: OcrToken) -> bool:
    centre_a, centre_b = a.box.y + a.box.h / 2, b.box.y + b.box.h / 2
    return abs(centre_a - centre_b) < 0.5 * min(a.box.h, b.box.h) and b.box.x >= a.box.x


def split_lines(tokens: Sequence[OcrToken]) -> list[list[OcrToken]]:
    """Group tokens (in reading order) into printed lines."""
    lines: list[list[OcrToken]] = []
    for token in tokens:
        if lines and _same_line(lines[-1][-1], token):
            lines[-1].append(token)
        else:
            lines.append([token])
    return lines


def line_evidence(tokens: Sequence[OcrToken], score: float, status: EvidenceStatus = "verified") -> list[Evidence]:
    return [
        Evidence(
            image_id=line[0].image_id,
            text=" ".join(t.text for t in line),
            box=union_box([t.box for t in line]),
            token_ids=[t.token_id for t in line],
            match_score=round(score, 3),
            status=status,
        )
        for line in split_lines(tokens)
    ]


def box_from_2d(box_2d: Box2d | None) -> Box | None:
    """Gemini convention [ymin, xmin, ymax, xmax] on 0..1000 -> normalised Box; None if malformed."""
    if box_2d is None or len(box_2d) != 4:
        return None
    ymin, xmin, ymax, xmax = (min(1000.0, max(0.0, float(v))) / 1000 for v in box_2d)
    if xmax <= xmin or ymax <= ymin:
        return None
    return Box(x=round(xmin, 4), y=round(ymin, 4), w=round(xmax - xmin, 4), h=round(ymax - ymin, 4))


def _length_ok(candidate: str, target: str, minimum: float) -> bool:
    return minimum * len(target) <= len(candidate) <= MAX_LENGTH_FACTOR * len(target) + LENGTH_SLACK


def _cited_tokens(token_ids: Sequence[str], image_id: str, index: TokenIndex) -> list[OcrToken]:
    tokens = {index.by_id[t].token_id: index.by_id[t] for t in token_ids
              if t in index.by_id and index.by_id[t].image_id == image_id}
    return sorted(tokens.values(), key=lambda t: index.position[t.token_id])


def _best_window(text: str, image_tokens: list[OcrToken], anchor: int | None) -> tuple[float, list[OcrToken]]:
    target, target_compact = norm(text), compact(text)
    best: tuple[float, float, float] = (-1.0, -1.0, 0.0)
    best_tokens: list[OcrToken] = []
    for start in range(len(image_tokens)):
        for end in range(start + 1, min(start + MAX_WINDOW, len(image_tokens)) + 1):
            window = image_tokens[start:end]
            window_text = " ".join(t.text for t in window)
            window_compact = compact(window_text)
            if len(window_compact) > MAX_LENGTH_FACTOR * len(target_compact) + LENGTH_SLACK:
                break
            if not _length_ok(window_compact, target_compact, MIN_WINDOW_LENGTH):
                continue
            window_norm = norm(window_text)
            key = (
                fuzz.partial_ratio(target, window_norm),
                fuzz.ratio(target, window_norm),
                -abs(start - anchor) if anchor is not None else 0.0,
            )
            if key > best:
                best, best_tokens = key, window
    return best[0], best_tokens


def align_span(
    text: str, token_ids: Sequence[str], box_2d: Box2d | None, image_id: str, index: TokenIndex,
) -> Alignment:
    cited = _cited_tokens(token_ids, image_id, index)
    if cited and compact(text):
        joined = " ".join(t.text for t in cited)
        score = fuzz.token_set_ratio(norm(text), norm(joined))
        if score >= CITED_MIN_SCORE and _length_ok(compact(joined), compact(text), 0.0):
            return Alignment("verified", line_evidence(cited, score / 100), joined)

    image_tokens = index.by_image.get(image_id, [])
    if compact(text) and image_tokens:
        anchor = index.position[cited[0].token_id] if cited else None
        score, window = _best_window(text, image_tokens, anchor)
        if score >= WINDOW_MIN_SCORE:
            return Alignment("verified", line_evidence(window, score / 100), " ".join(t.text for t in window))

    box = box_from_2d(box_2d)
    if box is not None:
        return Alignment("approximate", [Evidence(image_id=image_id, text=text, box=box, status="approximate")])
    return Alignment("unverified", [Evidence(image_id=image_id, text=text, status="unverified")])


def single_evidence(alignment: Alignment) -> Evidence:
    """Merge multi-line evidence into one (contract fields that hold a single Evidence)."""
    if len(alignment.evidence) == 1:
        return alignment.evidence[0]
    first = alignment.evidence[0]
    boxes = [e.box for e in alignment.evidence if e.box is not None]
    return first.model_copy(update={
        "text": " ".join(e.text for e in alignment.evidence),
        "box": union_box(boxes) if boxes else None,
        "token_ids": [t for e in alignment.evidence for t in e.token_ids],
    })


def _checked_amount(
    key: str, value: LLMNutrientValue, alignment: Alignment, issues: list[str],
) -> tuple[float | None, Readability]:
    """The number the engine may use: printed OCR text wins; a number not on the photo is dropped."""
    if value.readability == "unreadable":
        return None, "unreadable"
    if alignment.ocr_text is not None:
        ocr_amount = parse_number(alignment.ocr_text)
        if ocr_amount is None:
            return None, "unreadable"
        if value.amount is not None and numbers_differ(value.amount, ocr_amount):
            issues.append(f"{MISMATCH_ISSUE}:{key}")
        return ocr_amount, value.readability
    if alignment.status == "approximate":
        return value.amount, "partial"      # located only by the model's own box: not cross-checked
    issues.append(f"{NOT_ON_PHOTO_ISSUE}:{key}")
    return None, "unreadable"               # nowhere on the photo: never pass on a possibly invented number


# ------------------------------------------------------------------------------------------------
# Panel assembly
# ------------------------------------------------------------------------------------------------
@dataclass
class PanelExtraction:
    """One photo's extraction as contract objects (ids are provisional until merge.assign_ids)."""
    image_id: str
    ingredients: list[Ingredient]
    ingredients_section: SectionStatus
    allergen_statements: list[AllergenStatement]
    allergen_section: SectionStatus
    nutrition: NutritionTable | None
    nutrition_section: SectionStatus
    veg_mark: VegMark
    claims: list[Claim]
    evidence_count: dict[EvidenceStatus, int] = field(default_factory=dict)


class _PanelAligner:
    def __init__(self, panel: LLMPanel, image_id: str, index: TokenIndex, citations: Sequence[str]) -> None:
        self.panel = panel
        self.image_id = image_id
        self.index = index
        self.citations = citations          # the model's word number n -> token id
        self.counts: dict[EvidenceStatus, int] = {"verified": 0, "approximate": 0, "unverified": 0}

    def ids(self, numbers: Sequence[int]) -> list[str]:
        return [self.citations[n] for n in numbers if 0 <= n < len(self.citations)]

    def align(self, text: str, numbers: Sequence[int], box_2d: Box2d | None) -> Alignment:
        alignment = align_span(text, self.ids(numbers), box_2d, self.image_id, self.index)
        self.counts[alignment.status] += 1
        return alignment

    def section(self, section: LLMSection, extra_issues: Iterable[str] = (), readable: bool = True) -> SectionStatus:
        tokens = _cited_tokens(self.ids(section.unreadable_token_ids), self.image_id, self.index)
        regions = line_evidence(tokens, 0.0) if tokens else []
        for item in section.unreadable_boxes:
            box = box_from_2d(item.box_2d)
            if box is not None:
                regions.append(Evidence(image_id=self.image_id, text="", box=box, status="approximate"))
        issues = list(dict.fromkeys([*section.issues, *extra_issues]))
        if regions and "unreadable_span" not in issues and "truncated_at_image_edge" not in issues:
            issues.append("unreadable_span")
        complete = section.complete and section.presence == "found" and not regions and readable
        return SectionStatus(presence=section.presence, complete=complete, issues=issues, unreadable_regions=regions)

    def ingredient(self, item: LLMIngredient, provisional_id: str, issues: list[str]) -> Ingredient:
        alignment = self.align(item.text, item.token_ids, item.box_2d)
        percentage = item.percentage
        if alignment.ocr_text is not None:
            ocr_percentage = parse_percentage(alignment.ocr_text)
            if ocr_percentage is not None:
                if percentage is not None and numbers_differ(percentage, ocr_percentage):
                    issues.append(MISMATCH_ISSUE)
                percentage = ocr_percentage
        return Ingredient(
            id=provisional_id,
            raw_text=clean_item_text(alignment.ocr_text or item.text),
            name=clean_item_text(item.text),
            percentage=percentage,
            evidence=alignment.evidence,
            readability=item.readability,
            confidence=alignment.confidence,
        )

    def ingredients(self, issues: list[str]) -> list[Ingredient]:
        items = self.panel.ingredients
        built = [self.ingredient(item, f"ing_{n}", issues) for n, item in enumerate(items)]

        def valid_parent(n: int) -> int | None:
            parent = items[n].parent_index
            if parent is None or not 0 <= parent < len(items) or parent == n or items[parent].parent_index is not None:
                return None
            inside = fuzz.partial_ratio(norm(items[n].text), norm(items[parent].text)) >= NESTED_MIN_SCORE
            return parent if inside else None

        children: dict[int, list[Ingredient]] = {}
        for n in range(len(items)):
            parent = valid_parent(n)
            if parent is not None:
                children.setdefault(parent, []).append(built[n])
        return [
            built[n].model_copy(update={"sub_ingredients": children.get(n, [])})
            for n in range(len(items)) if valid_parent(n) is None
        ]

    def nutrient_value(self, key: str, value: LLMNutrientValue, issues: list[str]) -> NutrientValue:
        alignment = self.align(value.text, value.token_ids, value.box_2d)
        amount, readability = _checked_amount(key, value, alignment, issues)
        return NutrientValue(
            basis=value.basis,
            amount=amount,
            unit=value.unit,
            raw_text=clean_item_text(alignment.ocr_text or value.text),
            evidence=single_evidence(alignment),
            readability=readability,
        )

    def nutrient_row(self, row: LLMNutrientRow, issues: list[str]) -> NutrientRow:
        return NutrientRow(
            key=row.key,
            raw_label=row.label,
            values=[self.nutrient_value(row.key, v, issues) for v in row.values],
        )

    def nutrition(self, nutrition: LLMNutrition | None, issues: list[str]) -> NutritionTable | None:
        if nutrition is None:
            return None
        return NutritionTable(
            serving_size=nutrition.serving_size,
            serving_unit=nutrition.serving_unit,
            servings_per_pack=nutrition.servings_per_pack,
            pack_size=nutrition.pack_size,
            pack_unit=nutrition.pack_unit,
            rows=[self.nutrient_row(r, issues) for r in nutrition.rows],
        )

    def veg_mark(self, mark: LLMVegMark) -> VegMark:
        box = box_from_2d(mark.box_2d)
        if mark.value == "not_found" or box is None:
            return VegMark(value=mark.value)
        evidence = Evidence(image_id=self.image_id, text=f"{mark.value} mark", box=box, status="approximate")
        return VegMark(value=mark.value, evidence=evidence)

    def build(self) -> PanelExtraction:
        p = self.panel
        ingredient_issues: list[str] = []
        ingredients = self.ingredients(ingredient_issues)
        all_clear = all(i.readability == "clear" for i in p.ingredients)
        statements = []
        for n, s in enumerate(p.allergen_statements):
            alignment = self.align(s.text, s.token_ids, s.box_2d)
            statements.append(AllergenStatement(
                id=f"alg_{n}", type=s.type, raw_text=clean_item_text(alignment.ocr_text or s.text),
                items=s.items, evidence=alignment.evidence,
            ))
        nutrition_issues: list[str] = []
        nutrition = self.nutrition(p.nutrition, nutrition_issues)
        nutrition_readable = nutrition is None or all(
            v.readability == "clear" for r in nutrition.rows for v in r.values
        )
        claims = []
        for n, c in enumerate(p.claims):
            alignment = self.align(c.text, c.token_ids, c.box_2d)
            claims.append(Claim(id=f"clm_{n}", raw_text=clean_item_text(alignment.ocr_text or c.text),
                                evidence=alignment.evidence))
        return PanelExtraction(
            image_id=self.image_id,
            ingredients=ingredients,
            ingredients_section=self.section(p.ingredients_section, ingredient_issues, readable=all_clear),
            allergen_statements=statements,
            allergen_section=self.section(p.allergen_section),
            nutrition=nutrition,
            nutrition_section=self.section(p.nutrition_section, nutrition_issues, readable=nutrition_readable),
            veg_mark=self.veg_mark(p.veg_mark),
            claims=claims,
            evidence_count=dict(self.counts),
        )


def align_panel(panel: LLMPanel, image_id: str, index: TokenIndex, citations: Sequence[str]) -> PanelExtraction:
    return _PanelAligner(panel, image_id, index, citations).build()


def panel_image_ids(panels: Sequence[LLMPanel], image_ids: Sequence[str]) -> list[str]:
    """Trust the model's image_id when valid and unused, otherwise fall back to the panel's position."""
    resolved: list[str] = []
    for n, panel in enumerate(panels):
        if panel.image_id in image_ids and panel.image_id not in resolved:
            resolved.append(panel.image_id)
        else:
            unused = [i for i in image_ids if i not in resolved]
            preferred = image_ids[n] if n < len(image_ids) and image_ids[n] in unused else None
            resolved.append(preferred or (unused[0] if unused else image_ids[min(n, len(image_ids) - 1)]))
    return resolved
