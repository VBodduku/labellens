import type { Basis, Evidence, NutrientRow as NutritionRow, Readability, ScanResult } from "../shared/contract";

export type NutritionBasisView = "per_100" | "per_serving" | "per_pack";

export interface NutritionCell {
  key: string;
  label: string;
  amount: number | null;
  unit: string;
  readability: Readability;
  suspect: boolean;
  edited: boolean;
  /** Worked out from another basis (serving or pack size), not printed in this column. */
  derived: boolean;
  /** Field path of the extraction value this cell shows; null for derived (whole-pack) values. */
  fieldPath: string | null;
  rawText: string;
  evidence: Evidence | null;
}

const UNIT_BY_SUFFIX: Record<string, string> = { kcal: "kcal", g: "g", mg: "mg" };

function unitFromKey(key: string): string {
  const suffix = key.split("_").pop() ?? "";
  return UNIT_BY_SUFFIX[suffix] ?? "";
}

function extractionBasis(view: NutritionBasisView, per100Unit: "g" | "ml"): Basis {
  if (view === "per_serving") return "per_serving";
  return per100Unit === "ml" ? "per_100ml" : "per_100g";
}

/**
 * A row the engine has no key for ("MUFA", "Omega-3"): its per-100 or whole-pack amount, worked out from a clear
 * per-serving value the same way the engine does for the others (only when the serving is weighed in the same
 * unit as the 100; never across g and ml).
 */
function scaledOther(
  values: NutritionRow["values"],
  view: NutritionBasisView,
  table: NonNullable<ScanResult["extraction"]["nutrition"]>,
  per100Unit: "g" | "ml",
): number | undefined {
  const serving = values.find((value) => value.basis === "per_serving" && value.readability === "clear" && value.amount != null);
  if (!serving || serving.amount == null) return undefined;
  if (view === "per_100" && table.serving_size && table.serving_unit === per100Unit) {
    return (serving.amount * 100) / table.serving_size;
  }
  if (view === "per_pack" && table.servings_per_pack) return serving.amount * table.servings_per_pack;
  return undefined;
}

/**
 * Rows for the nutrition table. Per 100 g/ml and per serving come from the label's own values (editable);
 * whole pack comes from the engine's derived `per_pack` (read-only). Values the engine normalised but the
 * label did not print fall back to `nutrition_analysis.per_100`. A row without a standard key shows its
 * printed label.
 */
export function nutritionRows(result: ScanResult, view: NutritionBasisView): NutritionCell[] {
  const table = result.extraction.nutrition;
  const rows = table?.rows ?? [];
  const analysis = result.nutrition_analysis;
  const suspect = new Set(analysis?.consistency.suspect_keys ?? []);
  const per100Unit = analysis?.per_100_unit ?? "g";
  const basis = extractionBasis(view, per100Unit);

  return rows.map((row, rowIndex) => {
    const valueIndex = row.values.findIndex((value) => value.basis === basis);
    const value = valueIndex >= 0 ? row.values[valueIndex] : undefined;
    const fallbackUnit = value?.unit || unitFromKey(row.key);
    const base = {
      key: row.key,
      label: row.raw_label,
      suspect: suspect.has(row.key),
      rawText: value?.raw_text ?? "",
      evidence: value?.evidence ?? null,
    };

    const other = row.key === "other" && table ? scaledOther(row.values, view, table, per100Unit) : undefined;

    if (view === "per_pack") {
      const amount = analysis?.per_pack[row.key] ?? other;
      return {
        ...base,
        amount: amount ?? null,
        unit: fallbackUnit,
        readability: amount === undefined ? ("unreadable" as const) : ("clear" as const),
        edited: false,
        derived: true,
        fieldPath: null,
      };
    }

    if (!value) {
      const derived = view === "per_100" ? (analysis?.per_100[row.key] ?? other) : undefined;
      return {
        ...base,
        amount: derived ?? null,
        unit: fallbackUnit,
        readability: derived === undefined ? ("unreadable" as const) : ("clear" as const),
        edited: false,
        derived: true,
        fieldPath: null,
      };
    }

    return {
      ...base,
      amount: value.amount ?? null,
      unit: fallbackUnit,
      readability: value.readability,
      edited: value.corrected_by_user,
      derived: false,
      fieldPath: `nutrition.rows[${rowIndex}].values[${valueIndex}].amount`,
    };
  });
}

/** Whether the label shows enough to offer the per-serving view. */
export function hasServingValues(result: ScanResult): boolean {
  return (result.extraction.nutrition?.rows ?? []).some((row) => row.values.some((value) => value.basis === "per_serving"));
}
