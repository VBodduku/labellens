import type { NutritionAnalysis } from "../shared/contract";

export type ProteinBand = "excellent" | "veryGood" | "good" | "moderate" | "poor" | "veryPoor";

interface Band {
  band: ProteinBand;
  max: number;
  color: string;
}

const VERY_POOR: Band = { band: "veryPoor", max: Infinity, color: "hsl(355 72% 36%)" };

/** Calories-per-protein bands, best first: each covers ratios above the previous band's max up to its own (inclusive). */
export const BANDS: readonly Band[] = [
  { band: "excellent", max: 10, color: "hsl(145 70% 36%)" },
  { band: "veryGood", max: 15, color: "hsl(100 62% 42%)" },
  { band: "good", max: 20, color: "hsl(50 92% 46%)" },
  { band: "moderate", max: 30, color: "hsl(28 92% 50%)" },
  { band: "poor", max: 50, color: "hsl(4 78% 50%)" },
  VERY_POOR,
];

export const NO_PROTEIN_COLOR = "hsl(220 10% 18%)";

/** Ratio range of each equal-width scale segment, from the left (less protein) to the right (more protein). */
const SEGMENTS: readonly (readonly [number, number])[] = [[100, 50], [50, 30], [30, 20], [20, 15], [15, 10], [10, 4]];

export type ProteinRatio =
  | { kind: "ratio"; kcalPerGram: number; band: ProteinBand; color: string; position: number; energy: number; protein: number }
  | { kind: "no_protein"; energy: number }
  | { kind: "unavailable"; reason: "missing" | "suspect" | "no_energy" };

export function ratioBand(kcalPerGram: number): Band {
  return BANDS.find((item) => kcalPerGram <= item.max) ?? VERY_POOR;
}

/** Marker position (0–100 % from the left), linear inside each band's equal-width segment. */
export function scalePosition(kcalPerGram: number): number {
  for (const [i, [from, to]] of SEGMENTS.entries()) {
    if (kcalPerGram > to) return ((i + Math.max(0, from - kcalPerGram) / (from - to)) / SEGMENTS.length) * 100;
  }
  return 100;
}

/**
 * Calories per gram of protein from the engine's per-100 values (already converted from kJ). Values the
 * consistency check marks as possibly misread are never used: the card says so instead of rating a guess.
 */
export function proteinRatio(analysis: NutritionAnalysis | null | undefined): ProteinRatio {
  const energy = analysis?.per_100.energy_kcal;
  const protein = analysis?.per_100.protein_g;
  if (energy === undefined || protein === undefined) return { kind: "unavailable", reason: "missing" };
  const suspect = analysis?.consistency.suspect_keys ?? [];
  if (suspect.includes("energy_kcal") || suspect.includes("protein_g")) return { kind: "unavailable", reason: "suspect" };
  if (energy <= 0) return { kind: "unavailable", reason: "no_energy" };
  if (protein <= 0) return { kind: "no_protein", energy };
  const kcalPerGram = energy / protein;
  const { band, color } = ratioBand(kcalPerGram);
  return { kind: "ratio", kcalPerGram, band, color, position: scalePosition(kcalPerGram), energy, protein };
}
