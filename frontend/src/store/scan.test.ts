import { beforeEach, describe, expect, it, vi } from "vitest";
import type * as ApiModule from "../api";
import type { Profile, RecheckRequest } from "../shared/contract";

vi.mock("idb-keyval", () => ({ get: vi.fn(async () => undefined), set: vi.fn(async () => undefined), del: vi.fn(async () => undefined) }));
const recheck = vi.fn();
vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof ApiModule>();
  return { ...actual, api: { ...actual.api, recheck: (...args: unknown[]) => recheck(...args) } };
});

const { fixtureProfiles, fixtureScanResult } = await import("../api/fixtures");
const { ApiError } = await import("../api/errors");
const { useScanStore } = await import("./scan");

describe("scan store recheck", () => {
  beforeEach(() => {
    recheck.mockReset();
    useScanStore.setState({ result: structuredClone(fixtureScanResult), scanProfiles: fixtureProfiles, status: "done", recheckError: null, corrections: [] });
  });

  it("rechecks with a new family and the new language, keeping the profiles it used", async () => {
    const family: Profile[] = [fixtureProfiles[0]!];
    recheck.mockImplementation(async (request: RecheckRequest) => ({ ...fixtureScanResult, lang: request.lang }));
    await useScanStore.getState().recheck("te", family);
    const request = recheck.mock.calls[0]?.[0] as RecheckRequest;
    expect(request.lang).toBe("te");
    expect(request.profiles).toEqual(family);
    expect(useScanStore.getState()).toMatchObject({ status: "done", scanProfiles: family });
    expect(useScanStore.getState().result?.lang).toBe("te");
  });

  it("ignores a recheck that was superseded by a newer one (no status flip, no loop)", async () => {
    let finishSecond: () => void = () => undefined;
    recheck
      .mockImplementationOnce(
        (_request: RecheckRequest, options: { signal: AbortSignal }) =>
          new Promise((_resolve, reject) => {
            options.signal.addEventListener("abort", () => reject(new ApiError("ABORTED", "replaced")));
          }),
      )
      .mockImplementationOnce(
        (request: RecheckRequest) =>
          new Promise((resolve) => {
            finishSecond = () => resolve({ ...fixtureScanResult, lang: request.lang });
          }),
      );
    const first = useScanStore.getState().recheck("te");
    const second = useScanStore.getState().recheck("te");
    await first;
    // The aborted first request must not report "done" while the second is still running.
    expect(useScanStore.getState().status).toBe("rechecking");
    finishSecond();
    await second;
    expect(useScanStore.getState()).toMatchObject({ status: "done", recheckError: null });
    expect(useScanStore.getState().result?.lang).toBe("te");
  });

  it("keeps the current result on screen when a recheck fails", async () => {
    recheck.mockRejectedValue(new ApiError("NETWORK", "offline"));
    await useScanStore.getState().recheck("hi");
    const state = useScanStore.getState();
    expect(state.status).toBe("done");
    expect(state.result?.scan_id).toBe(fixtureScanResult.scan_id);
    expect(state.recheckError?.code).toBe("NETWORK");
  });

  it("answers a demo-label recheck from the bundled fixtures when the backend is unreachable", async () => {
    useScanStore.setState({ isDemo: true });
    recheck.mockRejectedValue(new ApiError("NETWORK", "backend down"));
    await useScanStore.getState().recheck("hi");
    const state = useScanStore.getState();
    expect(state).toMatchObject({ status: "done", recheckError: null });
    expect(state.result?.lang).toBe("hi");
    useScanStore.setState({ isDemo: false });
  });
});

describe("scan store checkContradiction", () => {
  const disputed = (path: string) => ({
    id: "ctr_0", kind: "ai_vs_print" as const, key: "ai_vs_print:ai_value=15|nutrient=sodium_mg|value=150",
    message_key: "contradiction.ai_vs_print", message_params: {}, explanation: "", evidence: [], affects: [], field_path: path,
  });

  beforeEach(() => {
    recheck.mockReset();
    recheck.mockImplementation(async (request: RecheckRequest) => ({ ...fixtureScanResult, extraction: request.extraction }));
    useScanStore.setState({ result: structuredClone(fixtureScanResult), scanProfiles: fixtureProfiles, status: "done", recheckError: null, corrections: [] });
  });

  it("saves a label-vs-label check with the scan and rechecks, without touching any value", async () => {
    const item = { ...disputed("ingredients[10].name"), kind: "veg_mark" as const, key: "veg_mark:term=x" };
    await useScanStore.getState().checkContradiction(item, "en");
    const request = recheck.mock.calls[0]?.[0] as RecheckRequest;
    expect(request.extraction.checked_contradictions).toEqual(["veg_mark:term=x"]);
    expect(useScanStore.getState().corrections).toEqual([]);
  });

  it("confirms a disputed number as printed, which makes it usable", async () => {
    const extraction = fixtureScanResult.extraction;
    const row = extraction.nutrition!.rows.findIndex((r) => r.values[0]?.amount != null);
    const path = `nutrition.rows[${row}].values[0].amount`;
    await useScanStore.getState().checkContradiction(disputed(path), "en");
    const request = recheck.mock.calls[0]?.[0] as RecheckRequest;
    const value = request.extraction.nutrition!.rows[row]!.values[0]!;
    expect(value).toMatchObject({ amount: extraction.nutrition!.rows[row]!.values[0]!.amount, corrected_by_user: true, readability: "clear" });
    expect(request.extraction.checked_contradictions).toContain(disputed(path).key);
  });
});

describe("scan store comparison", () => {
  const panel = { id: "panel_a", file: new Blob(["a"]), url: "blob:a", hint: "back" as const };

  beforeEach(() => {
    recheck.mockReset();
    URL.revokeObjectURL = vi.fn();
    useScanStore.setState({
      panels: [panel],
      result: structuredClone(fixtureScanResult),
      scanProfiles: fixtureProfiles,
      corrections: [],
      status: "done",
      isDemo: false,
      pinned: null,
      pinnedStatus: "idle",
      pinnedError: null,
      swapped: false,
    });
  });

  it("sets the current scan aside as product A and starts an empty scan for product B", async () => {
    await useScanStore.getState().startCompare();
    const state = useScanStore.getState();
    expect(state.pinned?.result.scan_id).toBe(fixtureScanResult.scan_id);
    expect(state.pinned?.panels).toEqual([panel]);
    expect(state).toMatchObject({ result: null, panels: [], status: "idle", swapped: false });
  });

  it("swaps A into the result screen and remembers that A still comes first", async () => {
    await useScanStore.getState().startCompare();
    const b = { ...structuredClone(fixtureScanResult), scan_id: "scan_b" };
    useScanStore.setState({ result: b, status: "done" });
    await useScanStore.getState().swapCompare();
    const state = useScanStore.getState();
    expect(state.result?.scan_id).toBe(fixtureScanResult.scan_id);
    expect(state.pinned?.result.scan_id).toBe("scan_b");
    expect(state.swapped).toBe(true);
  });

  it("rechecks product A for another family without touching the current scan's request", async () => {
    await useScanStore.getState().startCompare();
    const family: Profile[] = [fixtureProfiles[0]!];
    recheck.mockImplementation(async (request: RecheckRequest) => ({ ...fixtureScanResult, reports: fixtureScanResult.reports.slice(0, 1), lang: request.lang }));
    await useScanStore.getState().recheckPinned(family, "en");
    const state = useScanStore.getState();
    expect((recheck.mock.calls[0]?.[0] as RecheckRequest).profiles).toEqual(family);
    expect(state.pinned).toMatchObject({ scanProfiles: family });
    expect(state.pinned?.result.reports).toHaveLength(1);
    expect(state).toMatchObject({ pinnedStatus: "idle", pinnedError: null, status: "idle" });
  });

  it("keeps product A's results when its recheck fails, and says so", async () => {
    await useScanStore.getState().startCompare();
    recheck.mockRejectedValue(new ApiError("NETWORK", "offline"));
    await useScanStore.getState().recheckPinned([fixtureProfiles[0]!], "en");
    const state = useScanStore.getState();
    expect(state.pinned?.scanProfiles).toEqual(fixtureProfiles);
    expect(state.pinnedError?.code).toBe("NETWORK");
  });

  it("stops comparing", async () => {
    await useScanStore.getState().startCompare();
    await useScanStore.getState().stopCompare();
    expect(useScanStore.getState()).toMatchObject({ pinned: null, swapped: false });
  });
});
