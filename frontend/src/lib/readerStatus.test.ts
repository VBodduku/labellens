import { describe, expect, it } from "vitest";
import type { HealthResponse } from "../shared/contract";
import { readerStatus } from "./readerStatus";

const health = (gemini: boolean, ollama: boolean): HealthResponse => ({
  status: gemini || ollama ? "ok" : "degraded",
  providers: { gemini, ollama },
  engine_mode: "real",
  contract_version: "1.0.1",
});

describe("readerStatus", () => {
  it("uses the AI reader whenever Gemini is up", () => {
    expect(readerStatus(health(true, false))).toBe("ai");
    expect(readerStatus(health(true, true))).toBe("ai");
  });

  it("warns about the slower on-device reader when only Ollama is up", () => {
    expect(readerStatus(health(false, true))).toBe("local");
  });

  it("warns about basic reading when no AI reader is up", () => {
    expect(readerStatus(health(false, false))).toBe("basic");
  });

  it("says nothing until the backend has answered", () => {
    expect(readerStatus(null)).toBeNull();
  });
});
