import type { Lang } from "../shared/contract";

export function localeFor(lang: Lang): string {
  return `${lang}-IN`;
}

const numberFormats = new Map<Lang, Intl.NumberFormat>();

/** Locale-aware number formatting (Indian grouping, up to 2 decimals). */
export function formatNumber(value: number, lang: Lang): string {
  let format = numberFormats.get(lang);
  if (!format) {
    format = new Intl.NumberFormat(localeFor(lang), { maximumFractionDigits: 2 });
    numberFormats.set(lang, format);
  }
  return format.format(value);
}

const orLists = new Map<Lang, Intl.ListFormat>();

/** Joins items with the locale's word for "or" ("onion or garlic", "प्याज़ या लहसुन"). */
export function joinWithOr(items: string[], lang: Lang): string {
  let format = orLists.get(lang);
  if (!format) {
    format = new Intl.ListFormat(localeFor(lang), { type: "disjunction", style: "long" });
    orLists.set(lang, format);
  }
  return format.format(items);
}

const andLists = new Map<Lang, Intl.ListFormat>();

/** Joins items with the locale's word for "and". */
export function joinWithAnd(items: string[], lang: Lang): string {
  let format = andLists.get(lang);
  if (!format) {
    format = new Intl.ListFormat(localeFor(lang), { type: "conjunction", style: "long" });
    andLists.set(lang, format);
  }
  return format.format(items);
}
