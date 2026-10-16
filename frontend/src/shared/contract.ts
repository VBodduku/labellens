/**
 * LabelLens shared contract (TypeScript mirror of shared/contract.py).
 *
 * FROZEN after the initial commit on `main`. If you change one file you MUST change the other in the
 * same commit. Only ADD optional fields.
 *
 * Conventions: boxes are normalised 0..1 (top-left origin); image ids are "img_0".."img_2" in upload
 * order; languages are "en" | "hi" | "te"; UI text for verdicts comes from message_key + message_params
 * rendered through the frontend i18n files, never from free LLM text.
 */

export const CONTRACT_VERSION = "1.0.0";

export type Lang = "en" | "hi" | "te";

export const ALLERGEN_CATEGORIES = [
  "milk", "egg", "peanut", "tree_nut", "soy", "wheat", "gluten", "fish", "crustacean",
  "mollusc", "sesame", "mustard", "celery", "lupin", "sulphite",
] as const;
export const DIET_CATEGORIES = [
  "meat", "poultry", "fish_derived", "egg_derived", "dairy", "honey", "insect_derived",
  "gelatin", "animal_derived", "alcohol", "onion", "garlic", "root_vegetable",
  "added_sugar", "sugar_alias", "polyol", "artificial_sweetener", "palm_oil", "caffeine",
  "added_msg",
] as const;
export const CATEGORIES = [...ALLERGEN_CATEGORIES, ...DIET_CATEGORIES] as const;

export type Origin = "plant" | "animal" | "insect" | "synthetic" | "mineral" | "microbial" | "varies" | "unknown";

// ---------------------------------------------------------------- geometry, evidence, images
export interface Box { x: number; y: number; w: number; h: number }

export type EvidenceStatus = "verified" | "approximate" | "unverified";

export interface Evidence {
  image_id: string;
  text: string;
  box?: Box | null;
  token_ids: string[];
  match_score: number;
  status: EvidenceStatus;
}

export type QualityIssue = "blurry" | "glare" | "too_dark" | "low_resolution" | "cropped_edge";

export interface ImageQuality {
  ok: boolean;
  blur_score: number;
  glare_ratio: number;
  brightness: number;
  issues: QualityIssue[];
}

export type PanelHint = "front" | "back" | "side" | "unknown";

export interface ImageInfo {
  image_id: string;
  width: number;
  height: number;
  panel_hint: PanelHint;
  quality: ImageQuality;
}

export interface OcrToken {
  token_id: string;
  image_id: string;
  text: string;
  box: Box;
  confidence: number;
}

// ---------------------------------------------------------------- extraction
export type Readability = "clear" | "partial" | "unreadable";

export interface Ingredient {
  id: string;
  raw_text: string;
  name: string;
  percentage?: number | null;
  sub_ingredients: Ingredient[];
  evidence: Evidence[];
  readability: Readability;
  confidence: number;
}

export type StatementType = "contains" | "may_contain" | "facility" | "free_from";

export interface AllergenStatement {
  id: string;
  type: StatementType;
  raw_text: string;
  items: string[];
  evidence: Evidence[];
}

export type VegMarkValue = "veg" | "non_veg" | "not_found" | "unclear";
export interface VegMark { value: VegMarkValue; evidence?: Evidence | null }

export interface Claim { id: string; raw_text: string; evidence: Evidence[] }

export const NUTRIENT_KEYS = [
  "energy_kcal", "protein_g", "carbohydrate_g", "total_sugars_g", "added_sugars_g",
  "total_fat_g", "saturated_fat_g", "trans_fat_g", "cholesterol_mg", "sodium_mg",
  "fibre_g", "other",
] as const;
export type NutrientKey = (typeof NUTRIENT_KEYS)[number];

export type Basis = "per_100g" | "per_100ml" | "per_serving" | "per_pack";

export interface NutrientValue {
  basis: Basis;
  amount?: number | null;
  unit: string;
  raw_text: string;
  evidence?: Evidence | null;
  readability: Readability;
  corrected_by_user: boolean;
}

export interface NutrientRow { key: string; raw_label: string; values: NutrientValue[] }

export interface NutritionTable {
  serving_size?: number | null;
  serving_unit?: "g" | "ml" | null;
  servings_per_pack?: number | null;
  pack_size?: number | null;
  pack_unit?: "g" | "ml" | null;
  rows: NutrientRow[];
}

export type SectionPresence = "found" | "partial" | "not_found";

export interface SectionStatus {
  presence: SectionPresence;
  complete: boolean;
  issues: string[];
  unreadable_regions: Evidence[];
}

export interface RetryRecord { reason: string; action: string; outcome: string }

export type Provider = "gemini" | "ollama" | "ocr_only" | "fixture";

export interface ExtractionMeta {
  provider: Provider;
  model: string;
  attempts: number;
  retries: RetryRecord[];
  duration_ms: number;
  cache_hit: boolean;
}

export interface Correction {
  field_path: string;
  old_value: string | number | null;
  new_value: string | number;
  at: string;
}

export interface LabelExtraction {
  scan_id: string;
  images: ImageInfo[];
  ocr_tokens: OcrToken[];
  product_name?: string | null;
  languages_detected: string[];
  ingredients: Ingredient[];
  ingredients_section: SectionStatus;
  nutrition?: NutritionTable | null;
  nutrition_section: SectionStatus;
  allergen_statements: AllergenStatement[];
  allergen_section: SectionStatus;
  veg_mark: VegMark;
  claims: Claim[];
  user_corrections: Correction[];
  meta: ExtractionMeta;
}

// ---------------------------------------------------------------- profiles
export type RestrictionKind = "allergy" | "intolerance" | "diet" | "health_limit" | "avoid";
export type Severity = "strict" | "preference";

export interface Threshold {
  nutrient: string;
  max_value: number;
  basis: "per_100g" | "per_100ml" | "per_serving";
  source_note?: string | null;
}

export interface Restriction {
  id: string;
  kind: RestrictionKind;
  key: string;
  label: string;
  severity: Severity;
  threshold?: Threshold | null;
  source_text?: string | null;
}

export interface Profile {
  profile_id: string;
  name: string;
  color?: string | null;
  restrictions: Restriction[];
}

export interface RestrictionCatalogItem {
  key: string;
  kind: RestrictionKind;
  label_en: string;
  default_severity: Severity;
  categories: string[];
  needs_threshold: boolean;
  default_threshold?: Threshold | null;
  description_en: string;
}

// ---------------------------------------------------------------- engine outputs
export type VerdictState = "conflict" | "possible" | "not_listed" | "unknown";
export type UnknownKind = "not_detected" | "undeterminable";
export type MatchSource = "kb" | "llm_interpretation" | "veg_mark" | "allergen_statement" | "nutrition";

export interface Match {
  ingredient_id?: string | null;
  term: string;
  canonical_id?: string | null;
  category?: string | null;
  source: MatchSource;
  note?: string | null;
}

export interface RestrictionResult {
  restriction_id: string;
  state: VerdictState;
  unknown_kind?: UnknownKind | null;
  reason_code: string;
  message_key: string;
  message_params: Record<string, string | number>;
  explanation: string;
  evidence: Evidence[];
  matches: Match[];
  confidence: number;
}

export interface ProfileReport {
  profile_id: string;
  overall: VerdictState;
  results: RestrictionResult[];
  summary?: string | null;
  summary_lang?: Lang | null;
}

export interface IngredientAnnotation {
  ingredient_id: string;
  canonical_ids: string[];
  categories: string[];
  origin: Origin;
  source: "kb" | "llm_interpretation" | "unresolved";
  note?: string | null;
}

export interface ConsistencyCheck {
  status: "consistent" | "inconsistent" | "insufficient_data";
  declared_kcal?: number | null;
  computed_kcal?: number | null;
  deviation_pct?: number | null;
  suspect_keys: string[];
  message_key: string;
}

export interface NutritionAnalysis {
  per_100: Record<string, number>;
  per_100_unit: "g" | "ml";
  per_pack: Record<string, number>;
  servings_per_pack?: number | null;
  consistency: ConsistencyCheck;
  notes: string[];
}

export type UnknownSection = "ingredients" | "nutrition" | "allergens" | "veg_mark" | "image";

export interface UnknownItem {
  section: UnknownSection;
  message_key: string;
  detail?: string | null;
  region?: Evidence | null;
}

export interface ScanResult {
  contract_version: string;
  scan_id: string;
  lang: Lang;
  created_at: string;
  extraction: LabelExtraction;
  annotations: IngredientAnnotation[];
  nutrition_analysis?: NutritionAnalysis | null;
  reports: ProfileReport[];
  unknowns: UnknownItem[];
}

// ---------------------------------------------------------------- HTTP API
// POST /api/scan  (multipart/form-data)
//   images:       1-3 files (field repeated), order defines img_0, img_1, img_2
//   profiles:     JSON string of Profile[]
//   lang:         "en" | "hi" | "te"
//   panel_hints:  optional JSON string of PanelHint[]
//   -> ScanResult
export interface RecheckRequest { extraction: LabelExtraction; profiles: Profile[]; lang: Lang }

export interface AskRequest { question: string; lang: Lang; scan: ScanResult; profiles: Profile[] }
export interface ToolCallTrace { tool: string; args: Record<string, unknown>; result_summary: string }
export interface VerdictRef { profile_id: string; restriction_id?: string | null }
export interface AskResponse {
  answer: string;
  lang: Lang;
  grounded: boolean;
  tool_calls: ToolCallTrace[];
  evidence: Evidence[];
  verdict_refs: VerdictRef[];
  refusal?: string | null;
}

export interface ProfileParseRequest { text: string; lang: Lang }
export interface ProfileParseResponse {
  profiles: Profile[];
  unparsed: string[];
  warnings: string[];
  needs_confirmation: boolean;
}

export interface ExplainRequest { term: string; lang: Lang }
export interface ExplainResponse {
  term: string;
  canonical_id?: string | null;
  display_name: string;
  description: string;
  origin: Origin;
  categories: string[];
  source: "kb" | "llm";
  caution?: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  providers: Record<string, boolean>;
  engine_mode: "stub" | "real";
  contract_version: string;
}

export interface ErrorResponse { error_code: string; message: string; retry_after_s?: number | null }

/** Worst-first ordering used for `overall` and for sorting results in the UI. */
export const VERDICT_ORDER: VerdictState[] = ["conflict", "possible", "unknown", "not_listed"];
