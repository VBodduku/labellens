import { describe, expect, it } from "vitest";
import { fixtureScanResult } from "../api/fixtures";
import type { RestrictionResult } from "../shared/contract";
import { confirmationCorrections, confirmPrompt, editTargetFor, ingredientPath } from "./confirmations";
import { applyCorrections } from "./corrections";

const extraction = fixtureScanResult.extraction;
const result = (profileId: string, restrictionId: string): RestrictionResult => {
  const found = fixtureScanResult.reports.find((r) => r.profile_id === profileId)?.results.find((r) => r.restriction_id === restrictionId);
  if (!found) throw new Error(`fixture result ${restrictionId} missing`);
  return found;
};

describe("confirm prompts", () => {
  it("asks about an ingredient whose source the label leaves open", () => {
    expect(confirmPrompt(result("p_lakshmi", "r_lakshmi_jain"))).toEqual({
      ingredientId: "ing_10",
      term: "Natural Flavours",
      categories: ["onion", "garlic"],
      allowPresent: true,
    });
  });

  it("never asks about a finding the label states outright", () => {
    expect(confirmPrompt(result("p_aarav", "r_aarav_peanut"))).toBeNull();
    expect(confirmPrompt(result("p_aarav", "r_aarav_treenut"))).toBeNull();      // a statement, not an ingredient
  });

  it("an unknown ingredient can only be confirmed absent", () => {
    const unknown: RestrictionResult = {
      ...result("p_lakshmi", "r_lakshmi_jain"),
      state: "unknown",
      reason_code: "UNKNOWN_UNRESOLVED_TERM",
      message_params: { term: "Natural Flavours", category: "onion|garlic" },
    };
    expect(confirmPrompt(unknown)?.allowPresent).toBe(false);
  });
});

describe("saving a confirmation", () => {
  it("writes one correction per category onto the ingredient", () => {
    const prompt = confirmPrompt(result("p_lakshmi", "r_lakshmi_jain"));
    if (!prompt) throw new Error("no prompt");
    const corrections = confirmationCorrections(extraction, prompt, "absent", new Date("2026-10-17T10:00:00Z"));
    expect(corrections.map((c) => [c.field_path, c.new_value])).toEqual([
      ["ingredients[10].confirmations.onion", "absent"],
      ["ingredients[10].confirmations.garlic", "absent"],
    ]);
    const patched = applyCorrections(extraction, corrections);
    expect(patched.ingredients[10]?.confirmations).toEqual({ onion: "absent", garlic: "absent" });
    expect(patched.ingredients[10]?.name).toBe("Natural Flavours");
    expect(patched.user_corrections).toHaveLength(2);
  });

  it("finds nested ingredients", () => {
    const nested = { ...extraction, ingredients: [{ ...extraction.ingredients[0]!, sub_ingredients: [{ ...extraction.ingredients[1]!, id: "ing_0_0" }] }] };
    expect(ingredientPath(nested.ingredients, "ing_0_0")).toBe("ingredients[0].sub_ingredients[0]");
  });
});

describe("fixing one side of a contradiction", () => {
  it("opens the ingredient or the nutrient value it names", () => {
    expect(editTargetFor(extraction, "ingredients[1].name")).toMatchObject({ kind: "ingredient", current: "Peanuts (22%)" });
    expect(editTargetFor(extraction, "nutrition.rows[3].values[0].amount")).toMatchObject({ kind: "nutrient", current: 38 });
    expect(editTargetFor(extraction, "veg_mark.value")).toBeNull();
  });
});
