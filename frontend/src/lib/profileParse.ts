import type { Profile, Restriction, RestrictionCatalogItem, Severity } from "../shared/contract";
import { createId } from "./ids";

/** Avatar colours, picked in order for new family members (dark text stays readable on each). */
export const PROFILE_COLORS = ["#ff7a59", "#7c9cff", "#5fd3a5", "#f5c451", "#c58bff", "#ff8fb1", "#4fc3d9", "#a3d977"] as const;

/** First palette colour not already used (cycles when everyone has one). */
export function nextColor(used: readonly (string | null | undefined)[]): string {
  const taken = new Set(used.filter(Boolean).map((color) => color?.toLowerCase()));
  return PROFILE_COLORS.find((color) => !taken.has(color.toLowerCase())) ?? PROFILE_COLORS[used.length % PROFILE_COLORS.length]!;
}

/** A new restriction from a catalog entry, with the catalog's default severity and threshold. */
export function restrictionFromCatalog(item: RestrictionCatalogItem, severity: Severity = item.default_severity): Restriction {
  return {
    id: createId("r"),
    kind: item.kind,
    key: item.key,
    label: item.label_en,
    severity,
    threshold: item.needs_threshold && item.default_threshold ? { ...item.default_threshold } : null,
    source_text: null,
  };
}

/**
 * Turns confirmed parse proposals into profiles to save: fresh ids (never trust ids from the parser),
 * colours for anyone without one, and no empty names.
 */
export function finalizeParsedProfiles(proposed: Profile[], existing: Profile[]): Profile[] {
  const used: (string | null | undefined)[] = existing.map((profile) => profile.color);
  return proposed
    .filter((profile) => profile.name.trim().length > 0)
    .map((profile) => {
      const color = profile.color ?? nextColor(used);
      used.push(color);
      return {
        ...profile,
        profile_id: createId("p"),
        name: profile.name.trim(),
        color,
        restrictions: profile.restrictions.map((restriction) => ({ ...restriction, id: createId("r") })),
      };
    });
}
