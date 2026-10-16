import { describe, expect, it } from "vitest";
import en from "./i18n/en.json";
import hi from "./i18n/hi.json";
import { LANGS, type Dictionary } from "./i18n/resources";
import te from "./i18n/te.json";

const dictionaries: Record<(typeof LANGS)[number], Dictionary> = { en, hi, te };

/** Product principle: never tell anyone a product is "safe", "healthy" or "guaranteed" (CSS `safe-area` is not wording). */
const FORBIDDEN = /\b(safe|safely|healthy|guaranteed?)\b(?!-area)/i;

const sources = import.meta.glob(["./**/*.{ts,tsx}", "!./**/*.test.{ts,tsx}", "!./shared/**"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("user-facing wording", () => {
  it.each(LANGS)("%s.json never uses forbidden reassurance words", (lang) => {
    const offenders = Object.entries(dictionaries[lang]).filter(([, text]) => FORBIDDEN.test(text));
    expect(offenders).toEqual([]);
  });

  it("source files never hard-code forbidden reassurance words", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
    const offenders = Object.entries(sources)
      .filter(([, text]) => FORBIDDEN.test(text))
      .map(([file]) => file);
    expect(offenders).toEqual([]);
  });
});
