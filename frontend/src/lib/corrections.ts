import type { Correction, Ingredient, LabelExtraction } from "../shared/contract";
import { parsePath, formatPath, setAtPath, getAtPath } from "./fieldPath";

/**
 * Applies user corrections to an extraction: patches each field, flags corrected nutrient values
 * with `corrected_by_user`, and records the corrections in `user_corrections`. A corrected value or
 * ingredient counts as readable (the user read it off the pack), so the engine uses it; a renamed
 * ingredient's `raw_text` follows so verdict messages quote what the user confirmed. A confirmation
 * (`ingredients[4].confirmations.animal_derived`) records what the user read on the pack for one category.
 */
export function applyCorrections(extraction: LabelExtraction, corrections: Correction[]): LabelExtraction {
  let patched = extraction;
  for (const correction of corrections) {
    const segments = parsePath(correction.field_path);
    if (segments.at(-2) === "confirmations") {
      patched = applyConfirmation(patched, formatPath(segments.slice(0, -2)), String(segments.at(-1)), correction.new_value);
      continue;
    }
    patched = setAtPath(patched, correction.field_path, correction.new_value);
    const parentPath = formatPath(segments.slice(0, -1));
    if (typeof getAtPath(patched, parentPath) !== "object") continue;
    const isNutrientValue = segments[0] === "nutrition" && segments.includes("values");
    if (isNutrientValue) {
      patched = setAtPath(patched, `${parentPath}.corrected_by_user`, true);
      patched = setAtPath(patched, `${parentPath}.readability`, "clear");
    }
    if (segments[0] === "ingredients" && segments.at(-1) === "name") {
      patched = setAtPath(patched, `${parentPath}.raw_text`, correction.new_value);
      patched = setAtPath(patched, `${parentPath}.readability`, "clear");
    }
  }
  return { ...patched, user_corrections: [...extraction.user_corrections, ...corrections] };
}

function applyConfirmation(extraction: LabelExtraction, ingredientPath: string, category: string, value: string | number): LabelExtraction {
  const ingredient = getAtPath(extraction, ingredientPath) as Ingredient | undefined;
  if (!ingredient || (value !== "present" && value !== "absent")) return extraction;
  return setAtPath(extraction, ingredientPath, { ...ingredient, confirmations: { ...ingredient.confirmations, [category]: value } });
}

export function makeCorrection(
  extraction: LabelExtraction,
  fieldPath: string,
  newValue: string | number,
  at: Date = new Date(),
): Correction {
  const current = getAtPath(extraction, fieldPath);
  const oldValue = typeof current === "string" || typeof current === "number" ? current : null;
  return { field_path: fieldPath, old_value: oldValue, new_value: newValue, at: at.toISOString() };
}
