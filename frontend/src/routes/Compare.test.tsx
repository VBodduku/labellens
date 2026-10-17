import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fixtureCatalog, fixtureProfiles, fixtureScanResult } from "../api/fixtures";
import { initI18n } from "../i18n";
import type { ScanResult } from "../shared/contract";
import { useScanStore } from "../store/scan";
import Compare from "./Compare";

vi.mock("../components/profiles/useCatalog", () => ({
  useCatalog: () => ({ status: "ready", items: fixtureCatalog, error: null, retry: () => undefined }),
}));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** Product B: no peanuts in a fully read list, much less sugar per 100 g. */
function productB(): ScanResult {
  const b = structuredClone(fixtureScanResult);
  b.scan_id = "scan_b";
  b.extraction.product_name = "Masala Namkeen";
  b.extraction.ingredients = b.extraction.ingredients.filter((ingredient) => ingredient.id !== "ing_1");
  b.annotations = b.annotations.filter((annotation) => annotation.ingredient_id !== "ing_1");
  b.nutrition_analysis!.per_100 = { ...b.nutrition_analysis!.per_100, total_sugars_g: 4 };
  return b;
}

describe("Compare screen", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeAll(() => {
    initI18n("en");
  });

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  function render() {
    act(() =>
      root.render(
        <MemoryRouter>
          <Compare />
        </MemoryRouter>,
      ),
    );
    return container.textContent ?? "";
  }

  it("asks for a first product when nothing is set aside", () => {
    useScanStore.setState({ hydrated: true, pinned: null, result: null, status: "idle" });
    expect(render()).toContain("Nothing to compare yet");
  });

  it("asks for product B once product A is set aside", () => {
    useScanStore.setState({
      hydrated: true,
      result: null,
      status: "idle",
      pinned: { panels: [], result: fixtureScanResult, scanProfiles: fixtureProfiles, corrections: [], isDemo: true },
    });
    expect(render()).toContain("Scan the second product");
  });

  it("shows both products for each person, the differences and the per-100 table", () => {
    useScanStore.setState({
      hydrated: true,
      status: "done",
      isDemo: true,
      swapped: false,
      panels: [],
      result: productB(),
      scanProfiles: fixtureProfiles,
      pinned: { panels: [], result: fixtureScanResult, scanProfiles: fixtureProfiles, corrections: [], isDemo: true },
      pinnedStatus: "idle",
      pinnedError: null,
    });
    const text = render();
    expect(text).toContain("Compare products");
    expect(text).toContain("Masala Namkeen");
    for (const profile of fixtureProfiles) expect(text).toContain(profile.name);
    expect(text).toContain("A lists Peanuts (22%) (peanut); B doesn't.");
    expect(text).toMatch(/B has 89% less total sugars per 100 g than A\./);
    expect(text).toContain("Can't read");
    expect(text).not.toMatch(/\b(safe|healthy|healthier|better)\b/i);
  });
});
