import { describe, expect, it } from "vitest";
import { dictionaries, LANGS } from "./i18n/resources";

/** Product principle: never tell anyone a product is "safe", "healthy" or "guaranteed". */
const FORBIDDEN = /\b(safe|safely|healthy|guaranteed?)\b/i;

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
