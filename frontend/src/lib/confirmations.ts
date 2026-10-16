import type { EditTarget } from "../components/label/CorrectionEditor";
import type {
  Contradiction,
  Correction,
  Ingredient,
  LabelExtraction,
  NutrientRow,
  NutrientValue,
  RestrictionResult,
} from "../shared/contract";
import { makeCorrection } from "./corrections";
import { formatPath, getAtPath, parsePath } from "./fieldPath";

/** Results the user can settle by reading the pack: an ingredient whose source is unclear, guessed by AI, or unknown. */
const CONFIRMABLE = new Set(["POSSIBLE_AMBIGUOUS_SOURCE", "POSSIBLE_LLM_INTERPRETATION", "UNKNOWN_UNRESOLVED_TERM"]);

export type ConfirmValue = "present" | "absent";

export interface ConfirmPrompt {
  ingredientId: string;
  term: string;
  categories: string[];
  /** An unknown ingredient can only be confirmed absent; "contains" needs a real ingredient name (use Fix). */
  allowPresent: boolean;
}

export function confirmPrompt(result: RestrictionResult): ConfirmPrompt | null {
  if (!CONFIRMABLE.has(result.reason_code)) return null;
  const categories = String(result.message_params.category ?? "").split("|").filter(Boolean);
  const match = result.matches.find((candidate) => candidate.ingredient_id);
  if (!match?.ingredient_id || categories.length === 0) return null;
  return {
    ingredientId: match.ingredient_id,
    term: String(result.message_params.term ?? match.term),
    categories,
    allowPresent: result.reason_code !== "UNKNOWN_UNRESOLVED_TERM",
  };
}

export function ingredientPath(ingredients: Ingredient[], id: string, prefix = "ingredients"): string | null {
  for (const [index, ingredient] of ingredients.entries()) {
    const path = `${prefix}[${index}]`;
    if (ingredient.id === id) return path;
    const nested = ingredientPath(ingredient.sub_ingredients, id, `${path}.sub_ingredients`);
    if (nested) return nested;
  }
  return null;
}

/** One correction per category, e.g. `ingredients[4].confirmations.animal_derived = "absent"`. */
export function confirmationCorrections(
  extraction: LabelExtraction,
  prompt: ConfirmPrompt,
  value: ConfirmValue,
  at: Date = new Date(),
): Correction[] {
  const path = ingredientPath(extraction.ingredients, prompt.ingredientId);
  if (!path) return [];
  return prompt.categories.map((category) => makeCorrection(extraction, `${path}.confirmations.${category}`, value, at));
}

/** The correction sheet for one side of a contradiction (an ingredient name or a nutrient amount). */
export function editTargetFor(extraction: LabelExtraction, fieldPath: string): EditTarget | null {
  const segments = parsePath(fieldPath);
  const parent = getAtPath(extraction, formatPath(segments.slice(0, -1)));
  if (segments[0] === "ingredients" && segments.at(-1) === "name") {
    const ingredient = parent as Ingredient | undefined;
    return ingredient ? { kind: "ingredient", fieldPath, current: ingredient.name, rawText: ingredient.raw_text } : null;
  }
  if (segments[0] === "nutrition" && segments.at(-1) === "amount") {
    const value = parent as NutrientValue | undefined;
    const row = getAtPath(extraction, formatPath(segments.slice(0, 3))) as NutrientRow | undefined;
    return value && row
      ? { kind: "nutrient", fieldPath, label: row.raw_label, current: value.amount ?? null, unit: value.unit, rawText: value.raw_text }
      : null;
  }
  return null;
}

/**
 * For a disputed number (the AI vs the photo's text, or two photos), checking the pack means "the pack says
 * this number": the value in use is confirmed as a correction, which makes it usable for every check.
 * Disagreements between two printed things (veg mark, "free from", claims) are only marked checked.
 */
export function confirmsPrintedNumber(extraction: LabelExtraction, contradiction: Contradiction): { fieldPath: string; value: number } | null {
  if ((contradiction.kind !== "ai_vs_print" && contradiction.kind !== "panels") || !contradiction.field_path) return null;
  const value = getAtPath(extraction, contradiction.field_path);
  return typeof value === "number" ? { fieldPath: contradiction.field_path, value } : null;
}
