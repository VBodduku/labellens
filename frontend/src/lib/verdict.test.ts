import { describe, expect, it } from "vitest";
import { sortWorstFirst, stateLabelKey, worstState } from "./verdict";

describe("verdict ordering", () => {
  it("sorts worst-first and keeps ties in their original order", () => {
    const items = [
      { id: "a", state: "not_listed" as const },
      { id: "b", state: "unknown" as const },
      { id: "c", state: "conflict" as const },
      { id: "d", state: "possible" as const },
      { id: "e", state: "conflict" as const },
    ];
    expect(sortWorstFirst(items).map((item) => item.id)).toEqual(["c", "e", "d", "b", "a"]);
  });

  it("finds the worst state", () => {
    expect(worstState(["not_listed", "unknown", "possible"])).toBe("possible");
    expect(worstState([])).toBeNull();
  });

  it("maps states to their label keys", () => {
    expect(stateLabelKey("possible")).toBe("state.possible");
    expect(stateLabelKey("unknown", "not_detected")).toBe("state.unknown.not_detected");
    expect(stateLabelKey("unknown")).toBe("state.unknown");
  });
});
