import { beforeAll, describe, expect, it } from "vitest";
import { MISSING_PARAM, renderMessage, renderMessageParts } from "./renderMessage";
import { loadDictionary } from "./resources";

beforeAll(async () => {
  await Promise.all([loadDictionary("hi"), loadDictionary("te")]);
});

describe("renderMessage", () => {
  it("translates a single category and keeps the label term verbatim", () => {
    expect(renderMessage("verdict.conflict.ingredient", { term: "Peanuts (22%)", category: "peanut" }, "en")).toBe(
      "Lists Peanuts (22%) — this counts as peanut.",
    );
  });

  it("joins several categories with the locale's word for 'or'", () => {
    expect(
      renderMessage("verdict.possible.ambiguous_source", { term: "Natural Flavours", category: "onion|garlic" }, "en"),
    ).toBe("Natural Flavours can come from onion or garlic sources; the label does not say which.");
    expect(renderMessage("verdict.unknown.truncated", { category: "milk|egg|soy" }, "en")).toBe(
      "Part of the ingredient list is cut off. No milk, egg or soy found in the readable part.",
    );
  });

  it("translates nutrient and basis ids and formats numbers", () => {
    expect(
      renderMessage(
        "verdict.conflict.threshold",
        { nutrient: "total_sugars_g", value: 38, unit: "g", basis: "per_100g", limit: 22.5 },
        "en",
      ),
    ).toBe("Total sugars is 38 g per 100 g, above your limit of 22.5 g.");
  });

  it("uses Indian digit grouping for large numbers", () => {
    expect(
      renderMessage(
        "verdict.not_listed.within_limit",
        { nutrient: "sodium_mg", value: 1250.5, unit: "mg", basis: "per_pack", limit: 100000 },
        "en",
      ),
    ).toBe("Sodium is 1,250.5 mg per pack, within your limit of 1,00,000 mg.");
  });

  it("marks term and item params as label segments for the mono font", () => {
    const parts = renderMessageParts("verdict.possible.may_contain", { item: "TREE NUTS" }, "en");
    expect(parts).toEqual([
      { text: "The label warns it may contain ", kind: "text" },
      { text: "TREE NUTS", kind: "label" },
      { text: ".", kind: "text" },
    ]);
  });

  it("shows a dash for a missing param instead of a raw placeholder", () => {
    expect(renderMessage("verdict.unknown.nutrient_missing", {}, "en")).toBe(`${MISSING_PARAM} is not readable on this label.`);
  });

  it("falls back to the key itself for an unknown message key", () => {
    expect(renderMessage("verdict.does_not_exist", {}, "en")).toBe("verdict.does_not_exist");
  });

  it("leaves an unknown category id readable", () => {
    expect(renderMessage("verdict.unknown.unreadable", { category: "mystery_bean" }, "en")).toBe(
      "Some ingredients are unreadable. No mystery_bean found in the readable part.",
    );
  });

  it("renders in other languages without losing params", () => {
    const text = renderMessage("verdict.possible.ambiguous_source", { term: "Natural Flavours", category: "onion|garlic" }, "hi");
    expect(text).toContain("Natural Flavours");
    expect(text).not.toContain("{");
  });

  describe("edge cases", () => {
    it("formats zero instead of treating it as missing", () => {
      expect(
        renderMessage("verdict.not_listed.within_limit", { nutrient: "trans_fat_g", value: 0, unit: "g", basis: "per_100g", limit: 0.2 }, "en"),
      ).toBe("Trans fat is 0 g per 100 g, within your limit of 0.2 g.");
    });

    it("keeps numeric strings as given (they are label text, not numbers)", () => {
      expect(renderMessage("nutrition.serving_small", { servings: "3" }, "en")).toBe(
        "This pack holds 3 servings. Values per pack are much higher than per serving.",
      );
    });

    it("ignores empty segments in a category list", () => {
      expect(renderMessage("verdict.unknown.unreadable", { category: "onion|" }, "en")).toBe(
        "Some ingredients are unreadable. No onion found in the readable part.",
      );
    });

    it("shows an unknown nutrient key as-is rather than failing", () => {
      expect(renderMessage("verdict.unknown.nutrient_missing", { nutrient: "vitamin_q" }, "en")).toBe(
        "vitamin_q is not readable on this label.",
      );
    });

    it("formats numbers for Telugu with Indian grouping", () => {
      expect(
        renderMessage("verdict.conflict.threshold", { nutrient: "sodium_mg", value: 1250, unit: "mg", basis: "per_pack", limit: 600 }, "te"),
      ).toContain("1,250");
    });
  });
});
