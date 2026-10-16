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

  it("keeps the current result on screen when a recheck fails", async () => {
    recheck.mockRejectedValue(new ApiError("NETWORK", "offline"));
    await useScanStore.getState().recheck("hi");
    const state = useScanStore.getState();
    expect(state.status).toBe("done");
    expect(state.result?.scan_id).toBe(fixtureScanResult.scan_id);
    expect(state.recheckError?.code).toBe("NETWORK");
  });
});
