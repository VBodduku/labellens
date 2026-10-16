import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fixtureScanResult } from "../../api/fixtures";
import { initI18n } from "../../i18n";
import { useScanStore } from "../../store/scan";
import { useUiStore } from "../../store/ui";
import { ConfirmPrompt } from "./ConfirmPrompt";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const prompt = { ingredientId: "ing_10", term: "Natural Flavours", categories: ["onion", "garlic"], allowPresent: true };

describe("ConfirmPrompt", () => {
  let container: HTMLDivElement;
  let root: Root;
  const addCorrections = vi.fn(async () => undefined);

  beforeAll(() => {
    initI18n("en");
  });

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    addCorrections.mockClear();
    useUiStore.setState({ lang: "en" });
    useScanStore.setState({ result: structuredClone(fixtureScanResult), status: "done", addCorrections });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const button = (label: string) => [...container.querySelectorAll("button")].find((b) => b.textContent?.includes(label));

  it("asks about the ingredient by name, for each category in the user's words", () => {
    act(() => root.render(<ConfirmPrompt prompt={prompt} />));
    expect(container.textContent).toContain("Check the pack: does Natural Flavours contain onion or garlic?");
  });

  it("saves one confirmation per category and rechecks in the current language", () => {
    act(() => root.render(<ConfirmPrompt prompt={prompt} />));
    act(() => button("No, it doesn't")?.click());
    const [corrections, lang] = addCorrections.mock.calls[0] as unknown as [{ field_path: string; new_value: string }[], string];
    expect(corrections.map((c) => [c.field_path, c.new_value])).toEqual([
      ["ingredients[10].confirmations.onion", "absent"],
      ["ingredients[10].confirmations.garlic", "absent"],
    ]);
    expect(lang).toBe("en");
  });

  it("offers only 'no' for an unknown ingredient (a 'yes' needs a real name, through Fix)", () => {
    act(() => root.render(<ConfirmPrompt prompt={{ ...prompt, allowPresent: false }} />));
    expect(button("Yes, it does")).toBeUndefined();
    expect(button("No, it doesn't")).toBeDefined();
  });

  it("can't be answered twice while the verdicts are being rechecked", () => {
    useScanStore.setState({ status: "rechecking" });
    act(() => root.render(<ConfirmPrompt prompt={prompt} />));
    expect(button("No, it doesn't")?.disabled).toBe(true);
  });
});
