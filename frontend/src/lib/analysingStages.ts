/** Stage changes driven by elapsed time only — honest about what is happening, no fake percentage. */
const STAGES = [
  { from: 0, key: "analysing.reading" },
  { from: 2000, key: "analysing.understanding" },
  { from: 5000, key: "analysing.verifying" },
  { from: 8000, key: "analysing.checking" },
] as const;

export function stageAt(elapsedMs: number, profileCount: number): (typeof STAGES)[number]["key"] {
  const reachable = STAGES.filter((stage) => stage.key !== "analysing.checking" || profileCount > 0);
  return [...reachable].reverse().find((stage) => elapsedMs >= stage.from)?.key ?? "analysing.reading";
}
