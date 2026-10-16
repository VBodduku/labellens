import { renderMessage } from "../i18n/renderMessage";
import { lookup } from "../i18n/resources";
import type { Lang, ProfileReport } from "../shared/contract";
import { sortWorstFirst } from "./verdict";

/** The grounded summary when it is in the current language; otherwise one built only from fixed message templates. */
export function profileSummary(report: ProfileReport, profileName: string, lang: Lang): string {
  if (report.summary && report.summary_lang === lang) return report.summary;
  return templateSummary(report, profileName, lang);
}

export function templateSummary(report: ProfileReport, profileName: string, lang: Lang): string {
  const overall = lookup(`overall.${report.overall}`, lang) ?? report.overall;
  const worst = sortWorstFirst(report.results)[0];
  const detail = worst ? renderMessage(worst.message_key, worst.message_params, lang) : "";
  return renderMessage("result.summary.template", { name: profileName, overall, detail }, lang).trim();
}
