"""
LabelLens shared contract (Python / Pydantic v2).

FROZEN after the initial commit on `main`. All three parts build against this file.

Change protocol:
  * Only ADD optional fields. Never rename, remove, or change the type of an existing field.
  * Any change is made on `main` in ONE commit that updates BOTH this file and shared/contract.ts,
    bumps CONTRACT_VERSION's patch number, and is announced to the whole team.
  * Every part then pulls `main` into its branch.

Conventions:
  * All boxes are normalised to the image: 0..1, origin top-left. (x, y) is the top-left corner.
  * Image ids are assigned by the backend in upload order: "img_0", "img_1", "img_2".
    The frontend maps them back to the local files it uploaded in the same order.
  * Language codes: "en", "hi", "te".
  * The engine never writes free-text explanations for the UI in hi/te. It returns a message_key +
    message_params; the frontend renders them from its i18n files (fixed, reviewed translations).
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

CONTRACT_VERSION = "1.0.0"

Lang = Literal["en", "hi", "te"]

# --------------------------------------------------------------------------------------------
# Fixed category vocabulary. The engine KB and any LLM interpretation may ONLY use these values.
# --------------------------------------------------------------------------------------------
ALLERGEN_CATEGORIES = [
    "milk", "egg", "peanut", "tree_nut", "soy", "wheat", "gluten", "fish", "crustacean",
    "mollusc", "sesame", "mustard", "celery", "lupin", "sulphite",
]
DIET_CATEGORIES = [
    "meat", "poultry", "fish_derived", "egg_derived", "dairy", "honey", "insect_derived",
    "gelatin", "animal_derived", "alcohol", "onion", "garlic", "root_vegetable",
    "added_sugar", "sugar_alias", "polyol", "artificial_sweetener", "palm_oil", "caffeine",
    "added_msg",
]
CATEGORIES = ALLERGEN_CATEGORIES + DIET_CATEGORIES

Origin = Literal["plant", "animal", "insect", "synthetic", "mineral", "microbial", "varies", "unknown"]


# --------------------------------------------------------------------------------------------
# Geometry, evidence, images
# --------------------------------------------------------------------------------------------
class Box(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)


EvidenceStatus = Literal[
    "verified",     # matched to OCR tokens on the photo (fuzzy score >= threshold)
    "approximate",  # location comes only from the vision model's own box, not OCR
    "unverified",   # could not be located on the photo at all
]


class Evidence(BaseModel):
    image_id: str
    text: str                       # exact source text as seen on the label
    box: Optional[Box] = None       # union box of the matched tokens
    token_ids: list[str] = []
    match_score: float = 0.0        # 0..1
    status: EvidenceStatus


QualityIssue = Literal["blurry", "glare", "too_dark", "low_resolution", "cropped_edge"]


class ImageQuality(BaseModel):
    ok: bool
    blur_score: float               # variance of Laplacian on a 1024px-long-side grayscale copy
    glare_ratio: float              # fraction of near-white saturated pixels
    brightness: float               # mean luminance 0..255
    issues: list[QualityIssue] = []


PanelHint = Literal["front", "back", "side", "unknown"]


class ImageInfo(BaseModel):
    image_id: str
    width: int
    height: int
    panel_hint: PanelHint = "unknown"
    quality: ImageQuality


class OcrToken(BaseModel):
    token_id: str                   # "img_0:t12"
    image_id: str
    text: str
    box: Box
    confidence: float


# --------------------------------------------------------------------------------------------
# Extraction (produced by Part 2)
# --------------------------------------------------------------------------------------------
Readability = Literal["clear", "partial", "unreadable"]


class Ingredient(BaseModel):
    id: str                         # "ing_3", sub-ingredients "ing_3_1"
    raw_text: str                   # exactly as printed, e.g. "Emulsifier (INS 322)"
    name: str                       # cleaned display name, e.g. "Emulsifier (INS 322)"
    percentage: Optional[float] = None
    sub_ingredients: list["Ingredient"] = []
    evidence: list[Evidence] = []
    readability: Readability = "clear"
    confidence: float = 1.0


StatementType = Literal["contains", "may_contain", "facility", "free_from"]


class AllergenStatement(BaseModel):
    id: str
    type: StatementType
    raw_text: str
    items: list[str]                # as printed, e.g. ["Peanut", "Milk"]
    evidence: list[Evidence] = []


VegMarkValue = Literal["veg", "non_veg", "not_found", "unclear"]


class VegMark(BaseModel):
    value: VegMarkValue
    evidence: Optional[Evidence] = None


class Claim(BaseModel):
    """Front-of-pack marketing claim, e.g. 'No added sugar'. Captured now, used by the stretch goal."""
    id: str
    raw_text: str
    evidence: list[Evidence] = []


# Canonical nutrient keys. Anything else uses key="other" and keeps raw_label.
NUTRIENT_KEYS = [
    "energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "added_sugars_g",
    "total_fat_g", "saturated_fat_g", "trans_fat_g", "cholesterol_mg", "sodium_mg",
    "fibre_g", "other",
]

Basis = Literal["per_100g", "per_100ml", "per_serving", "per_pack"]


class NutrientValue(BaseModel):
    basis: Basis
    amount: Optional[float] = None  # None when unreadable
    unit: str                       # "kcal", "kJ", "g", "mg", "mcg"
    raw_text: str
    evidence: Optional[Evidence] = None
    readability: Readability = "clear"
    corrected_by_user: bool = False


class NutrientRow(BaseModel):
    key: str                        # one of NUTRIENT_KEYS
    raw_label: str                  # e.g. "Total Sugars"
    values: list[NutrientValue]


class NutritionTable(BaseModel):
    serving_size: Optional[float] = None
    serving_unit: Optional[Literal["g", "ml"]] = None
    servings_per_pack: Optional[float] = None
    pack_size: Optional[float] = None
    pack_unit: Optional[Literal["g", "ml"]] = None
    rows: list[NutrientRow] = []


SectionPresence = Literal["found", "partial", "not_found"]


class SectionStatus(BaseModel):
    presence: SectionPresence
    complete: bool                  # True ONLY if the whole section was read end to end
    issues: list[str] = []          # e.g. ["truncated_at_image_edge", "unreadable_span"]
    unreadable_regions: list[Evidence] = []


class RetryRecord(BaseModel):
    reason: str                     # e.g. "nutrition_inconsistent", "ingredients_truncated"
    action: str                     # e.g. "reread_region:img_0", "ask_user_retake"
    outcome: str                    # e.g. "resolved", "unchanged", "skipped_rate_limit"


Provider = Literal["gemini", "ollama", "ocr_only", "fixture"]


class ExtractionMeta(BaseModel):
    provider: Provider
    model: str
    attempts: int = 1
    retries: list[RetryRecord] = []
    duration_ms: int = 0
    cache_hit: bool = False


class Correction(BaseModel):
    """A user fix applied in the UI ('that 0 g is actually 8 g')."""
    field_path: str                 # e.g. "nutrition.rows[3].values[0].amount" or "ingredients[ing_4].name"
    old_value: Union[str, float, None]
    new_value: Union[str, float]
    at: str                         # ISO timestamp


class LabelExtraction(BaseModel):
    scan_id: str
    images: list[ImageInfo]
    ocr_tokens: list[OcrToken] = []
    product_name: Optional[str] = None
    languages_detected: list[str] = []
    ingredients: list[Ingredient] = []
    ingredients_section: SectionStatus
    nutrition: Optional[NutritionTable] = None
    nutrition_section: SectionStatus
    allergen_statements: list[AllergenStatement] = []
    allergen_section: SectionStatus
    veg_mark: VegMark
    claims: list[Claim] = []
    user_corrections: list[Correction] = []
    meta: ExtractionMeta


# --------------------------------------------------------------------------------------------
# Profiles (owned by the user, stored in the browser)
# --------------------------------------------------------------------------------------------
RestrictionKind = Literal["allergy", "intolerance", "diet", "health_limit", "avoid"]
Severity = Literal["strict", "preference"]


class Threshold(BaseModel):
    nutrient: str                   # NUTRIENT_KEYS value, e.g. "total_sugars_g"
    max_value: float
    basis: Literal["per_100g", "per_100ml", "per_serving"] = "per_100g"
    source_note: Optional[str] = None


class Restriction(BaseModel):
    id: str
    kind: RestrictionKind
    key: str                        # catalog key, e.g. "peanut", "jain", "diabetes_sugar"
    label: str                      # display label in the user's language
    severity: Severity
    threshold: Optional[Threshold] = None
    source_text: Optional[str] = None   # what the user typed/said, if parsed


class Profile(BaseModel):
    profile_id: str
    name: str
    color: Optional[str] = None
    restrictions: list[Restriction]


class RestrictionCatalogItem(BaseModel):
    key: str
    kind: RestrictionKind
    label_en: str
    default_severity: Severity
    categories: list[str]           # subset of CATEGORIES this restriction cares about
    needs_threshold: bool = False
    default_threshold: Optional[Threshold] = None
    description_en: str


# --------------------------------------------------------------------------------------------
# Engine outputs (produced by Part 3, returned through Part 2)
# --------------------------------------------------------------------------------------------
VerdictState = Literal["conflict", "possible", "not_listed", "unknown"]
UnknownKind = Literal[
    "not_detected",     # section partly readable; nothing found in the readable part
    "undeterminable",   # section missing, required value missing, or labels don't carry this info
]
MatchSource = Literal["kb", "llm_interpretation", "veg_mark", "allergen_statement", "nutrition"]


class Match(BaseModel):
    ingredient_id: Optional[str] = None
    term: str
    canonical_id: Optional[str] = None
    category: Optional[str] = None
    source: MatchSource
    note: Optional[str] = None


class RestrictionResult(BaseModel):
    restriction_id: str
    state: VerdictState
    unknown_kind: Optional[UnknownKind] = None
    reason_code: str                # stable machine code, e.g. "CONFLICT_INGREDIENT"
    message_key: str                # key in shared/messages.en.json
    message_params: dict[str, Union[str, float]] = {}
    explanation: str                # English rendering of message_key (for logs, agent, fallback)
    evidence: list[Evidence] = []
    matches: list[Match] = []
    confidence: float = 1.0


class ProfileReport(BaseModel):
    profile_id: str
    overall: VerdictState           # worst-of: conflict > possible > unknown > not_listed
    results: list[RestrictionResult]
    summary: Optional[str] = None   # short grounded LLM summary in summary_lang (Part 2 fills)
    summary_lang: Optional[Lang] = None


class IngredientAnnotation(BaseModel):
    ingredient_id: str
    canonical_ids: list[str] = []
    categories: list[str] = []
    origin: Origin = "unknown"
    source: Literal["kb", "llm_interpretation", "unresolved"]
    note: Optional[str] = None


class ConsistencyCheck(BaseModel):
    status: Literal["consistent", "inconsistent", "insufficient_data"]
    declared_kcal: Optional[float] = None
    computed_kcal: Optional[float] = None
    deviation_pct: Optional[float] = None
    suspect_keys: list[str] = []
    message_key: str


class NutritionAnalysis(BaseModel):
    per_100: dict[str, float] = {}          # canonical key -> amount per 100 g/ml
    per_100_unit: Literal["g", "ml"] = "g"
    per_pack: dict[str, float] = {}         # canonical key -> amount for the whole pack
    servings_per_pack: Optional[float] = None
    consistency: ConsistencyCheck
    notes: list[str] = []                   # message keys, e.g. "nutrition.serving_small"


UnknownSection = Literal["ingredients", "nutrition", "allergens", "veg_mark", "image"]


class UnknownItem(BaseModel):
    section: UnknownSection
    message_key: str
    detail: Optional[str] = None
    region: Optional[Evidence] = None       # where to retake (image_id + box)


class ScanResult(BaseModel):
    contract_version: str = CONTRACT_VERSION
    scan_id: str
    lang: Lang
    created_at: str
    extraction: LabelExtraction
    annotations: list[IngredientAnnotation] = []
    nutrition_analysis: Optional[NutritionAnalysis] = None
    reports: list[ProfileReport] = []
    unknowns: list[UnknownItem] = []


# --------------------------------------------------------------------------------------------
# HTTP API bodies (Part 2 implements, Part 1 consumes). See docs/00_MASTER_SPEC.md §6.
# POST /api/scan is multipart: images (1-3 files), profiles (JSON string of list[Profile]),
# lang, panel_hints (optional JSON list of PanelHint). Returns ScanResult.
# --------------------------------------------------------------------------------------------
class RecheckRequest(BaseModel):
    """Re-run the engine after user corrections or profile/language changes. No new LLM extraction."""
    extraction: LabelExtraction
    profiles: list[Profile]
    lang: Lang = "en"


class AskRequest(BaseModel):
    question: str
    lang: Lang = "en"
    scan: ScanResult
    profiles: list[Profile]


class ToolCallTrace(BaseModel):
    tool: str
    args: dict = {}
    result_summary: str


class VerdictRef(BaseModel):
    profile_id: str
    restriction_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    lang: Lang
    grounded: bool                  # False only when the answer is a refusal/redirect
    tool_calls: list[ToolCallTrace] = []
    evidence: list[Evidence] = []
    verdict_refs: list[VerdictRef] = []
    refusal: Optional[str] = None   # e.g. "medical_advice", "not_on_label"


class ProfileParseRequest(BaseModel):
    text: str
    lang: Lang = "en"


class ProfileParseResponse(BaseModel):
    profiles: list[Profile]         # a sentence can describe several people
    unparsed: list[str] = []        # phrases we could not map — shown to the user
    warnings: list[str] = []
    needs_confirmation: bool = True


class ExplainRequest(BaseModel):
    term: str
    lang: Lang = "en"


class ExplainResponse(BaseModel):
    term: str
    canonical_id: Optional[str] = None
    display_name: str
    description: str
    origin: Origin = "unknown"
    categories: list[str] = []
    source: Literal["kb", "llm"]
    caution: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    providers: dict[str, bool]      # {"gemini": true, "ollama": false}
    engine_mode: Literal["stub", "real"]
    contract_version: str = CONTRACT_VERSION


class ErrorResponse(BaseModel):
    error_code: str                 # "BAD_IMAGE", "RATE_LIMITED", "LLM_UNAVAILABLE", "VALIDATION"
    message: str
    retry_after_s: Optional[int] = None


Ingredient.model_rebuild()
