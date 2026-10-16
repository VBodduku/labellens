import type { ScanResult } from "../shared/contract";

export function verdictKey(profileId: string, restrictionId: string): string {
  return `${profileId}:${restrictionId}`;
}

/** Keys (`profile:restriction`) whose verdict state differs between two results — drives the change animation. */
export function changedVerdicts(previous: ScanResult | null, next: ScanResult): string[] {
  if (!previous) return [];
  const before = new Map<string, string>();
  for (const report of previous.reports) {
    for (const result of report.results) {
      before.set(verdictKey(report.profile_id, result.restriction_id), `${result.state}:${result.unknown_kind ?? ""}`);
    }
  }
  const changed: string[] = [];
  for (const report of next.reports) {
    for (const result of report.results) {
      const key = verdictKey(report.profile_id, result.restriction_id);
      const previousState = before.get(key);
      if (previousState !== undefined && previousState !== `${result.state}:${result.unknown_kind ?? ""}`) changed.push(key);
    }
  }
  return changed;
}
