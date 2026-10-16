import { describe, expect, it } from "vitest";
import { stageAt } from "./analysingStages";

describe("analysing stages", () => {
  it("advances with elapsed time only", () => {
    expect(stageAt(0, 3)).toBe("analysing.reading");
    expect(stageAt(2500, 3)).toBe("analysing.understanding");
    expect(stageAt(6000, 3)).toBe("analysing.verifying");
    expect(stageAt(9000, 3)).toBe("analysing.checking");
  });

  it("never claims to check family members when there are none", () => {
    expect(stageAt(20000, 0)).toBe("analysing.verifying");
  });
});
