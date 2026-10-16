import { describe, expect, it } from "vitest";
import { CATEGORIES, NUTRIENT_KEYS } from "../shared/contract";
import catalog from "../shared/fixtures/catalog.json";
import messages from "../shared/messages.en.json";
import { dictionaries, LANGS } from "./resources";

const BASIS_IDS = ["per_100g", "per_100ml", "per_serving", "per_pack"];
const contentKeys = (dictionary: Record<string, string>) => Object.keys(dictionary).filter((key) => !key.startsWith("_"));

describe("translation files", () => {
  const messageEntries = Object.entries(messages).filter(([key]) => !key.startsWith("_"));

  it("en.json carries every shared message key with the exact English template", () => {
    for (const [key, template] of messageEntries) {
      expect(dictionaries.en[key], key).toBe(template);
    }
  });

  it("en.json names every category, nutrient and basis", () => {
    const required = [
      ...CATEGORIES.map((id) => `categories.${id}`),
      ...NUTRIENT_KEYS.map((key) => `nutrients.${key}`),
      ...BASIS_IDS.map((id) => `basis.${id}`),
    ];
    const missing = required.filter((key) => !dictionaries.en[key]);
    expect(missing).toEqual([]);
  });

  it.each(LANGS.filter((lang) => lang !== "en"))("%s.json has exactly the same keys as en.json", (lang) => {
    const enKeys = new Set(contentKeys(dictionaries.en));
    const langKeys = new Set(contentKeys(dictionaries[lang]));
    expect([...enKeys].filter((key) => !langKeys.has(key)), "missing").toEqual([]);
    expect([...langKeys].filter((key) => !enKeys.has(key)), "extra").toEqual([]);
  });

  it.each(LANGS.filter((lang) => lang !== "en"))("%s.json is actually translated (not English placeholders)", (lang) => {
    const keys = contentKeys(dictionaries.en);
    const translated = keys.filter((key) => dictionaries[lang][key] !== dictionaries.en[key]);
    expect(translated.length / keys.length).toBeGreaterThan(0.95);
  });

  it("names every restriction key in the catalog (fixture plus the engine's extra allergens)", () => {
    const keys = [...catalog.map((item) => item.key), "mollusc", "celery", "lupin"];
    for (const lang of LANGS) {
      expect(keys.filter((key) => !dictionaries[lang][`restrictions.${key}`]), lang).toEqual([]);
    }
  });

  it.each(LANGS)("%s.json keeps every {placeholder} from the English text", (lang) => {
    const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
    for (const key of contentKeys(dictionaries.en)) {
      const translated = dictionaries[lang][key] ?? "";
      expect(placeholders(translated), `${lang}:${key}`).toEqual(placeholders(dictionaries.en[key] ?? ""));
    }
  });
});
