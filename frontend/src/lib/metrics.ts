import { VERDICT_ORDER, type VerdictState } from "../shared/contract";

/**
 * What the About page may say about accuracy, parsed from public/metrics.json (Part 3's
 * engine/eval/reports/metrics.json). Synthetic runs test software behaviour only and are never shown as
 * accuracy; only real-packet runs produce numbers.
 */
export type MetricsView =
  | { kind: "pending" }
  | { kind: "synthetic"; packets: number }
  | {
      kind: "real";
      packets: number;
      verdictAccuracy: number | null;
      dangerousMissRate: number | null;
      evidenceVerifiedRate: number | null;
      unknownRate: number | null;
      ingredientPrecision: number | null;
      ingredientRecall: number | null;
      averageLatencyMs: number | null;
      confusion: Record<VerdictState, Record<VerdictState, number>> | null;
      limitations: string[];
    }
  | { kind: "invalid" };

function num(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function confusionMatrix(value: unknown): Record<VerdictState, Record<VerdictState, number>> | null {
  if (typeof value !== "object" || value === null) return null;
  const table = value as Record<string, unknown>;
  const rows = {} as Record<VerdictState, Record<VerdictState, number>>;
  for (const expected of VERDICT_ORDER) {
    const row = table[expected];
    if (typeof row !== "object" || row === null) return null;
    rows[expected] = {} as Record<VerdictState, number>;
    for (const actual of VERDICT_ORDER) rows[expected][actual] = num((row as Record<string, unknown>)[actual]) ?? 0;
  }
  return rows;
}

export function parseMetrics(data: unknown): MetricsView {
  if (typeof data !== "object" || data === null) return { kind: "invalid" };
  const record = data as Record<string, unknown>;
  if (record.status === "pending") return { kind: "pending" };
  const realPackets = num(record.real_packets);
  if (realPackets === null) return { kind: "invalid" };
  if (record.dataset_kind !== "real" || realPackets === 0) return { kind: "synthetic", packets: num(record.packets) ?? 0 };
  return {
    kind: "real",
    packets: realPackets,
    verdictAccuracy: num(record.verdict_accuracy),
    dangerousMissRate: num(record.dangerous_miss_rate),
    evidenceVerifiedRate: num(record.evidence_verified_rate),
    unknownRate: num(record.unknown_rate),
    ingredientPrecision: num(record.ingredient_precision),
    ingredientRecall: num(record.ingredient_recall),
    averageLatencyMs: num(record.average_latency_ms),
    confusion: confusionMatrix(record.confusion_matrix),
    limitations: Array.isArray(record.limitations) ? record.limitations.filter((item): item is string => typeof item === "string") : [],
  };
}
