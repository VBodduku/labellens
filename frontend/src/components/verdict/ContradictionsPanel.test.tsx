import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fixtureProfiles, fixtureScanResult } from "../../api/fixtures";
import { initI18n } from "../../i18n";
import type { Contradiction } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { ContradictionsPanel } from "./ContradictionsPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const extraction = fixtureScanResult.extraction;
const flavours = extraction.ingredients[10]!;
const sodiumRow = extraction.nutrition!.rows.findIndex((row) => row.key === "sodium_mg");

const vegMark: Contradiction = {
  id: "ctr_0",
  kind: "veg_mark",
  key: "veg_mark:category=animal_derived|term=Natural Flavours",
  message_key: "contradiction.veg_mark",
  message_params: { term: "Natural Flavours", category: "animal_derived" },
  explanation: "",
  evidence: flavours.evidence,
  affects: [{ profile_id: "p_lakshmi", restriction_id: "r_lakshmi_jain" }],
  field_path: "ingredients[10].name",
};

const aiVsPrint: Contradiction = {
  ...vegMark,
  id: "ctr_1",
  kind: "ai_vs_print",
  key: "ai_vs_print:ai_value=15|nutrient=sodium_mg|value=150",
  message_key: "contradiction.ai_vs_print",
  message_params: { nutrient: "sodium_mg", ai_value: 15, value: 150 },
  field_path: `nutrition.rows[${sodiumRow}].values[0].amount`,
};

describe("ContradictionsPanel", () => {
  let container: HTMLDivElement;
  let root: Root;
  const onCheck = vi.fn();
  const onFix = vi.fn();

  beforeAll(() => {
    initI18n("en");
  });

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    onCheck.mockReset();
    onFix.mockReset();
    useUiStore.setState({ lang: "en" });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  function render(contradictions: Contradiction[], withNumber = extraction) {
    act(() =>
      root.render(
        <ContradictionsPanel contradictions={contradictions} extraction={withNumber} profiles={fixtureProfiles} onCheck={onCheck} onFix={onFix} />,
      ),
    );
  }

  const button = (label: string) => [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(label));

  it("shows nothing when the readings agree", () => {
    render([]);
    expect(container.innerHTML).toBe("");
  });

  it("states the disagreement, who it affects, and that it is not checked yet", () => {
    render([vegMark]);
    expect(container.textContent).toContain("The green vegetarian mark disagrees with Natural Flavours");
    expect(container.textContent).toContain("Affects: Lakshmi · Jain");
    expect(container.textContent).toContain("Not checked yet");
  });

  it("hands the item to the caller when the user checked the pack, and opens the fix for the misread word", () => {
    render([vegMark]);
    act(() => button("I checked the pack")?.click());
    expect(onCheck).toHaveBeenCalledWith(vegMark);
    act(() => button("Fix a misread")?.click());
    expect(onFix).toHaveBeenCalledWith(expect.objectContaining({ kind: "ingredient", fieldPath: "ingredients[10].name" }));
  });

  it("shows a saved check as checked by you, with no second check button", () => {
    render([{ ...vegMark, checked: true }]);
    expect(container.textContent).toContain("Checked by you");
    expect(button("I checked the pack")).toBeUndefined();
  });

  it("asks a disputed number as 'the pack says' the number in use", () => {
    const rows = extraction.nutrition!.rows.map((row, n) =>
      n === sodiumRow ? { ...row, values: [{ ...row.values[0]!, amount: 150 }, ...row.values.slice(1)] } : row,
    );
    render([aiVsPrint], { ...extraction, nutrition: { ...extraction.nutrition!, rows } });
    expect(button("The pack says 150")).toBeDefined();
    act(() => button("The pack says 150")?.click());
    expect(onCheck).toHaveBeenCalledWith(aiVsPrint);
  });
});
