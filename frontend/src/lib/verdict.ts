import { VERDICT_ORDER, type RestrictionResult, type UnknownKind, type VerdictState } from "../shared/contract";

export function verdictRank(state: VerdictState): number {
  return VERDICT_ORDER.indexOf(state);
}

/** Worst-first (conflict → possible → unknown → not_listed) by any state accessor; stable for ties. */
export function sortByStateWorstFirst<T>(items: readonly T[], stateOf: (item: T) => VerdictState): T[] {
  return items
    .map((item, index) => ({ item, index }))
    .sort((a, b) => verdictRank(stateOf(a.item)) - verdictRank(stateOf(b.item)) || a.index - b.index)
    .map(({ item }) => item);
}

export function sortWorstFirst<T extends { state: VerdictState }>(items: readonly T[]): T[] {
  return sortByStateWorstFirst(items, (item) => item.state);
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
