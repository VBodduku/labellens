import { renderMessage } from "../i18n/renderMessage";
import { lookup } from "../i18n/resources";
import type { Lang, Profile, ProfileReport } from "../shared/contract";
import { restrictionLabel } from "./restrictionLabel";
import { profileSummary } from "./templateSummary";
import { sortWorstFirst, stateLabelKey } from "./verdict";

export type ReadAloudMode = "short" | "full";

function sentence(text: string): string {
  const trimmed = text.trim();
  return /[.!?।]$/u.test(trimmed) ? trimmed : `${trimmed}.`;
}

/**
 * What read-aloud says for one family member, built only from fixed translated templates and the grounded
 * summary. Short = overall line + the most important result; Full = summary + every result.
 */
export function speechScript(report: ProfileReport, profile: Profile | undefined, lang: Lang, mode: ReadAloudMode): string {
  const name = profile?.name ?? report.profile_id;
  const results = sortWorstFirst(report.results);
  const describe = (index: number) => {
    const result = results[index];
    if (!result) return "";
    const restriction = profile?.restrictions.find((candidate) => candidate.id === result.restriction_id);
    const label = restriction ? restrictionLabel(restriction.key, restriction.label, lang) : result.restriction_id;
    const state = lookup(stateLabelKey(result.state, result.unknown_kind), lang) ?? result.state;
    return `${sentence(`${label}: ${state}`)} ${sentence(renderMessage(result.message_key, result.message_params, lang))}`;
  };

  if (mode === "short") {
    const overall = lookup(`overall.${report.overall}`, lang) ?? report.overall;
    return [sentence(`${name}: ${overall}`), describe(0)].filter(Boolean).join(" ");
  }
  return [sentence(profileSummary(report, name, lang)), ...results.map((_, index) => describe(index))].filter(Boolean).join(" ");
}
