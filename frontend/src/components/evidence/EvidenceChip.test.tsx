import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { fixtureScanResult } from "../../api/fixtures";
import { initI18n } from "../../i18n";
import { useUiStore } from "../../store/ui";
import { EvidenceChip } from "./EvidenceChip";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const peanuts = fixtureScanResult.reports[0]!.results[0]!.evidence[0]!;

describe("EvidenceChip", () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeAll(() => {
    initI18n("en");
  });

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    useUiStore.setState({ focusedEvidence: null });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("asks the viewer to focus its evidence, with a new nonce on every tap", () => {
    act(() => root.render(<EvidenceChip evidence={peanuts} state="conflict" />));
    const button = container.querySelector("button");
    expect(button?.textContent).toContain("Peanuts (22%)");
    act(() => button?.click());
    const first = useUiStore.getState().focusedEvidence;
    expect(first).toMatchObject({ evidence: peanuts, state: "conflict" });
    act(() => button?.click());
    expect(useUiStore.getState().focusedEvidence?.nonce).toBe((first?.nonce ?? 0) + 1);
  });

  it("says it couldn't locate unverified evidence instead of offering a zoom", () => {
    act(() => root.render(<EvidenceChip evidence={{ ...peanuts, status: "unverified", box: null }} state="possible" />));
    expect(container.querySelector("button")).toBeNull();
    expect(container.textContent).toContain("Couldn't locate on photo");
  });
});
