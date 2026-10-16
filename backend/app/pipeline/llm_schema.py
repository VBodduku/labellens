"""LLM-facing extraction schema: flat, every item cites OCR words by their number in that photo's
OCR list (`token_ids: [12, 13]`, ~1 output token each instead of ~6 for "img_0:t12"); the
pipeline maps the numbers back to real token ids (structure.Citations).

One level of nesting (panels) keeps evidence and multi-panel merging per photo; no recursion, so
Gemini's and Ollama's structured-output support can handle it. Boxes use Gemini's convention:
box_2d = [ymin, xmin, ymax, xmax] on a 0..1000 scale, only when no token matches.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from shared.contract import Basis, PanelHint, Readability, SectionPresence, StatementType, VegMarkValue

NutrientKey = Literal[
    "energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "added_sugars_g",
    "total_fat_g", "saturated_fat_g", "trans_fat_g", "cholesterol_mg", "sodium_mg",
    "fibre_g", "other",
]

Box2d = list[int]


class LLMIngredient(BaseModel):
    text: str
    token_ids: list[int] = []
    percentage: Optional[float] = None
    parent_index: Optional[int] = None
    readability: Readability = "clear"
    box_2d: Optional[Box2d] = None


class LLMUnreadableBox(BaseModel):
    box_2d: Box2d


class LLMSection(BaseModel):
    presence: SectionPresence
    complete: bool
    issues: list[str] = []
    unreadable_token_ids: list[int] = []
    unreadable_boxes: list[LLMUnreadableBox] = []


class LLMStatement(BaseModel):
    type: StatementType
    text: str
    items: list[str] = []
    token_ids: list[int] = []
    box_2d: Optional[Box2d] = None


class LLMNutrientValue(BaseModel):
    basis: Basis
    amount: Optional[float] = None
    unit: str
    text: str
    token_ids: list[int] = []
    readability: Readability = "clear"
    box_2d: Optional[Box2d] = None


class LLMNutrientRow(BaseModel):
    key: NutrientKey
    label: str
    values: list[LLMNutrientValue] = []


class LLMNutrition(BaseModel):
    serving_size: Optional[float] = None
    serving_unit: Optional[Literal["g", "ml"]] = None
    servings_per_pack: Optional[float] = None
    pack_size: Optional[float] = None
    pack_unit: Optional[Literal["g", "ml"]] = None
    rows: list[LLMNutrientRow] = []


class LLMVegMark(BaseModel):
    value: VegMarkValue
    box_2d: Optional[Box2d] = None


class LLMClaim(BaseModel):
    text: str
    token_ids: list[int] = []
    box_2d: Optional[Box2d] = None


class LLMPanel(BaseModel):
    image_id: str
    panel: PanelHint = "unknown"
    ingredients: list[LLMIngredient] = []
    ingredients_section: LLMSection
    allergen_statements: list[LLMStatement] = []
    allergen_section: LLMSection
    nutrition: Optional[LLMNutrition] = None
    nutrition_section: LLMSection
    veg_mark: LLMVegMark
    claims: list[LLMClaim] = []


class LLMExtraction(BaseModel):
    product_name: Optional[str] = None
    languages: list[str] = []
    panels: list[LLMPanel] = Field(min_length=1)
