import { VERDICT_ORDER, type RestrictionResult, type UnknownKind, type VerdictState } from "../shared/contract";

export function verdictRank(state: VerdictState): number {
  return VERDICT_ORDER.indexOf(state);
}

/** Worst-first (conflict → possible → unknown → not_listed); stable for equal states. */
export function sortWorstFirst<T extends { state: VerdictState }>(items: readonly T[]): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => verdictRank(a.item.state) - verdictRank(b.item.state) || a.index - b.index)
    .map(({ item }) => item);
}

export function worstState(states: readonly VerdictState[]): VerdictState | null {
  return states.reduce<VerdictState | null>(
    (worst, state) => (worst === null || verdictRank(state) < verdictRank(worst) ? state : worst),
    null,
  );
}

/** i18n key for a state's short label ("Conflict", "Check this", "Not detected", …). */
export function stateLabelKey(state: VerdictState, unknownKind?: UnknownKind | null): string {
  if (state === "unknown") return unknownKind ? `state.unknown.${unknownKind}` : "state.unknown";
  return `state.${state}`;
}

export function resultLabelKey(result: Pick<RestrictionResult, "state" | "unknown_kind">): string {
  return stateLabelKey(result.state, result.unknown_kind);
}
