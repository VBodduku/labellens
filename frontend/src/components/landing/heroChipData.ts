import { fixtureProfiles, fixtureScanResult } from "../../api/fixtures";
import type { Box, UnknownKind, VerdictState } from "../../shared/contract";

export interface HeroChip {
  id: string;
  profileName: string;
  profileColor: string;
  state: VerdictState;
  unknownKind: UnknownKind | null;
  /** Words as printed on the label; null when the region is unreadable (shown as a hatch). */
  word: string | null;
  /** Nutrient id for unreadable values, so the chip can name the row. */
  nutrient: string | null;
  boxes: Box[];
  /** Which side of the words the chip floats to, so neighbouring chips don't collide. */
  direction: "up" | "down";
}

/** The four flags the hero tells the demo story with (master spec §2), one per family moment. */
const PICKS = [
  { profileId: "p_aarav", restrictionId: "r_aarav_peanut", direction: "up", boxCount: 1 },
  { profileId: "p_lakshmi", restrictionId: "r_lakshmi_jain", direction: "down", boxCount: 2 },
  { profileId: "p_thatha", restrictionId: "r_thatha_sugar", direction: "up", boxCount: 1 },
  { profileId: "p_thatha", restrictionId: "r_thatha_sodium", direction: "down", boxCount: 1 },
] as const;

function buildChips(): HeroChip[] {
  return PICKS.flatMap((pick) => {
    const profile = fixtureProfiles.find((candidate) => candidate.profile_id === pick.profileId);
    const report = fixtureScanResult.reports.find((candidate) => candidate.profile_id === pick.profileId);
    const result = report?.results.find((candidate) => candidate.restriction_id === pick.restrictionId);
    if (!profile || !result) return [];
    const located = result.evidence.filter((evidence) => evidence.box && evidence.status !== "unverified");
    const boxes = located.slice(0, pick.boxCount).flatMap((evidence) => (evidence.box ? [evidence.box] : []));
    if (boxes.length === 0) return [];
    const term = result.message_params.term;
    const evidenceText = located[0]?.text ?? "";
    const word = typeof term === "string" ? term : evidenceText || null;
    const nutrient = result.message_params.nutrient;
    return [
      {
        id: result.restriction_id,
        profileName: profile.name,
        profileColor: profile.color ?? "var(--beam)",
        state: result.state,
        unknownKind: result.unknown_kind ?? null,
        word,
        nutrient: typeof nutrient === "string" ? nutrient : null,
        boxes,
        direction: pick.direction,
      },
    ];
  });
}

export const HERO_CHIPS: HeroChip[] = buildChips();

/** Fixture label aspect (width / height) — the hero packet and poster use the same proportions. */
export const LABEL_ASPECT = (() => {
  const image = fixtureScanResult.extraction.images[0];
  return image ? image.width / image.height : 1000 / 1400;
})();
