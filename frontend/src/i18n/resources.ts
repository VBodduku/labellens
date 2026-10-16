import type { Lang } from "../shared/contract";
import en from "./en.json";

export type Dictionary = Record<string, string>;

export const LANGS: readonly Lang[] = ["en", "hi", "te"];

/** English ships in the main bundle; Hindi and Telugu load on demand (keeps the first load small). */
export const dictionaries: Partial<Record<Lang, Dictionary>> & { en: Dictionary } = { en };

const LOADERS: Record<Exclude<Lang, "en">, () => Promise<Dictionary>> = {
  hi: () => import("./hi.json").then((module) => module.default),
  te: () => import("./te.json").then((module) => module.default),
};

export async function loadDictionary(lang: Lang): Promise<Dictionary> {
  const loaded = dictionaries[lang];
  if (loaded) return loaded;
  const dictionary = await LOADERS[lang as Exclude<Lang, "en">]();
  dictionaries[lang] = dictionary;
  return dictionary;
}

export function isLang(value: unknown): value is Lang {
  return typeof value === "string" && (LANGS as readonly string[]).includes(value);
}

/** Looks a key up in `lang` (if loaded), then English; undefined when neither has it. */
export function lookup(key: string, lang: Lang): string | undefined {
  return dictionaries[lang]?.[key] ?? dictionaries.en[key];
}
