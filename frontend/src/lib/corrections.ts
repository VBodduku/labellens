import type { Correction, LabelExtraction } from "../shared/contract";
import { parsePath, formatPath, setAtPath, getAtPath } from "./fieldPath";

/**
 * Applies user corrections to an extraction: patches each field, flags corrected nutrient values
 * with `corrected_by_user`, and records the corrections in `user_corrections`.
 */
export function applyCorrections(extraction: LabelExtraction, corrections: Correction[]): LabelExtraction {
  let patched = extraction;
  for (const correction of corrections) {
    patched = setAtPath(patched, correction.field_path, correction.new_value);
    const segments = parsePath(correction.field_path);
    const isNutrientValue = segments[0] === "nutrition" && segments.includes("values");
    if (isNutrientValue) {
      const valuePath = formatPath(segments.slice(0, -1));
      if (typeof getAtPath(patched, valuePath) === "object") {
        patched = setAtPath(patched, `${valuePath}.corrected_by_user`, true);
      }
    }
  }
  return { ...patched, user_corrections: [...extraction.user_corrections, ...corrections] };
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
