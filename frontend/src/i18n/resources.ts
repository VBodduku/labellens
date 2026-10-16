import type { Lang } from "../shared/contract";
import en from "./en.json";
import hi from "./hi.json";
import te from "./te.json";

export type Dictionary = Record<string, string>;

export const LANGS: readonly Lang[] = ["en", "hi", "te"];

export const dictionaries: Record<Lang, Dictionary> = { en, hi, te };

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as readonly string[]).includes(value);
}

/** Looks a key up in `lang`, then English; undefined when neither has it. */
export function lookup(key: string, lang: Lang): string | undefined {
  return dictionaries[lang][key] ?? dictionaries.en[key];
}
