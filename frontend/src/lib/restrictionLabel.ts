import { lookup } from "../i18n/resources";
import type { Lang } from "../shared/contract";

/** Translated restriction name (`restrictions.<key>`), falling back to the English label from the catalog/profile. */
export function restrictionLabel(key: string, fallback: string, lang: Lang): string {
  return lookup(`restrictions.${key}`, lang) ?? fallback;
}
