import { afterEach, describe, expect, it, vi } from "vitest";
import { applyCorrections, makeCorrection } from "../lib/corrections";
import { ApiError } from "./errors";
import { fixtureProfiles, fixtureScanResult } from "./fixtures";
import { MOCK_DELAYS_MS, mockApi, mockErrorFromUrl } from "./mock";

function setSearch(search: string) {
  window.history.replaceState(null, "", `/${search}`);
}

async function settle<T>(promise: Promise<T>, ms: number): Promise<T> {
  await vi.advanceTimersByTimeAsync(ms);
  return promise;
}

describe("mock API", () => {
  afterEach(() => {
    vi.useRealTimers();
    setSearch("");
  });

  it("reads the error code from ?mockError", () => {
    expect(mockErrorFromUrl("?mockError=RATE_LIMITED")).toBe("RATE_LIMITED");
    expect(mockErrorFromUrl("?mockError=nonsense")).toBeNull();
    expect(mockErrorFromUrl("")).toBeNull();
  });

  it("returns the fixture result for the demo family after a realistic delay", async () => {
    vi.useFakeTimers();
    const pending = mockApi.scan({ images: [new Blob(["x"])], profiles: fixtureProfiles, lang: "te" });
    const result = await settle(pending, MOCK_DELAYS_MS.scan);
    expect(result.lang).toBe("te");
    expect(result.reports.map((report) => report.profile_id)).toEqual(["p_aarav", "p_thatha", "p_lakshmi"]);
  });

  it("returns extraction only when no profiles are sent", async () => {
    vi.useFakeTimers();
    const result = await settle(mockApi.scan({ images: [new Blob(["x"])], profiles: [], lang: "en" }), MOCK_DELAYS_MS.scan);
    expect(result.reports).toEqual([]);
    expect(result.extraction.ingredients.length).toBeGreaterThan(0);
  });

  it("simulates RATE_LIMITED with retry_after when ?mockError=RATE_LIMITED", async () => {
    vi.useFakeTimers();
    setSearch("?mockError=RATE_LIMITED");
    const pending = mockApi.scan({ images: [new Blob(["x"])], profiles: [], lang: "en" });
    const assertion = expect(pending).rejects.toMatchObject({ code: "RATE_LIMITED", retryAfterS: 30, status: 429 });
    await vi.advanceTimersByTimeAsync(MOCK_DELAYS_MS.scan);
    await assertion;
    await expect(pending).rejects.toBeInstanceOf(ApiError);
  });

  it("keeps the simulated error even if the app navigates while the call is pending", async () => {
    vi.useFakeTimers();
    setSearch("?mockError=LLM_UNAVAILABLE");
    const pending = mockApi.scan({ images: [new Blob(["x"])], profiles: [], lang: "en" });
    const assertion = expect(pending).rejects.toMatchObject({ code: "LLM_UNAVAILABLE" });
    setSearch("");
    await vi.advanceTimersByTimeAsync(MOCK_DELAYS_MS.scan);
    await assertion;
  });

  it("rejects with ABORTED when the caller cancels", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const pending = mockApi.scan({ images: [new Blob(["x"])], profiles: [], lang: "en" }, { signal: controller.signal });
    controller.abort();
    await expect(pending).rejects.toMatchObject({ code: "ABORTED" });
  });

  it("echoes the corrected extraction on recheck", async () => {
    vi.useFakeTimers();
    const correction = makeCorrection(fixtureScanResult.extraction, "ingredients[10].name", "Natural Vanilla Flavour");
    const extraction = applyCorrections(fixtureScanResult.extraction, [correction]);
    const result = await settle(
      mockApi.recheck({ extraction, profiles: fixtureProfiles, lang: "en" }),
      MOCK_DELAYS_MS.recheck,
    );
    expect(result.extraction.ingredients[10]?.name).toBe("Natural Vanilla Flavour");
    expect(result.extraction.user_corrections).toEqual([correction]);
    expect(fixtureScanResult.extraction.ingredients[10]?.name).toBe("Natural Flavours");
  });
});
