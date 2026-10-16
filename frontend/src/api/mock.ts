import type { Profile, ProfileReport, ScanResult } from "../shared/contract";
import { ApiError, isServerErrorCode, type ServerErrorCode } from "./errors";
import {
  fixtureAsk,
  fixtureCatalog,
  fixtureExplain,
  fixtureHealth,
  fixtureProfileParse,
  fixtureScanResult,
} from "./fixtures";
import { unreadableScenario } from "./mockScenarios";
import type { LabelLensApi } from "./types";

/** Realistic latencies so loading states are visible during development and demos. */
export const MOCK_DELAYS_MS = {
  health: 250,
  catalog: 400,
  scan: 2500,
  recheck: 450,
  ask: 1200,
  parseProfile: 900,
  explain: 500,
} as const;

const MOCK_ERROR_MESSAGES: Record<ServerErrorCode, string> = {
  BAD_IMAGE: "The photo could not be used.",
  TOO_MANY_IMAGES: "At most 3 photos per scan.",
  RATE_LIMITED: "The AI service is busy. Try again shortly.",
  LLM_UNAVAILABLE: "The AI service is unavailable.",
  VALIDATION: "The request was not valid.",
  INTERNAL: "Something went wrong on the server.",
};

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new ApiError("ABORTED", "The request was cancelled"));
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      reject(new ApiError("ABORTED", "The request was cancelled"));
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** `?mockError=RATE_LIMITED` (any server error code) makes every mocked POST fail with that error. */
export function mockErrorFromUrl(search: string = globalThis.location?.search ?? ""): ServerErrorCode | null {
  const value = new URLSearchParams(search).get("mockError");
  return isServerErrorCode(value) ? value : null;
}

/** Reads ?mockError when the call starts (the app may navigate away while the mock is "working"). */
function throwIfMockError(code: ServerErrorCode | null): void {
  if (!code) return;
  throw new ApiError(code, MOCK_ERROR_MESSAGES[code], {
    status: code === "RATE_LIMITED" ? 429 : code === "INTERNAL" || code === "LLM_UNAVAILABLE" ? 503 : 400,
    retryAfterS: code === "RATE_LIMITED" ? 30 : null,
  });
}

/** Keeps only the fixture reports for profiles that were sent (no profiles → extraction only). */
function reportsFor(profiles: Profile[]): ProfileReport[] {
  const ids = new Set(profiles.map((profile) => profile.profile_id));
  return fixtureScanResult.reports.filter((report) => ids.has(report.profile_id));
}

function freshResult(overrides: Partial<ScanResult>): ScanResult {
  return { ...structuredClone(fixtureScanResult), created_at: new Date().toISOString(), ...overrides };
}

export const mockApi: LabelLensApi = {
  async health(options) {
    await delay(MOCK_DELAYS_MS.health, options?.signal);
    return structuredClone(fixtureHealth);
  },
  async catalog(options) {
    await delay(MOCK_DELAYS_MS.catalog, options?.signal);
    return structuredClone(fixtureCatalog);
  },
  async scan(input, options) {
    const failure = mockErrorFromUrl();
    await delay(MOCK_DELAYS_MS.scan, options?.signal);
    throwIfMockError(failure);
    if (input.images.length === 0) throw new ApiError("VALIDATION", "Add at least one photo.", { status: 422 });
    if (input.images.length > 3) throw new ApiError("TOO_MANY_IMAGES", MOCK_ERROR_MESSAGES.TOO_MANY_IMAGES, { status: 400 });
    const result = freshResult({ lang: input.lang, reports: structuredClone(reportsFor(input.profiles)) });
    return new URLSearchParams(globalThis.location?.search ?? "").get("mockScenario") === "unreadable"
      ? unreadableScenario(result, input.profiles)
      : result;
  },
  async recheck(request, options) {
    const failure = mockErrorFromUrl();
    await delay(MOCK_DELAYS_MS.recheck, options?.signal);
    throwIfMockError(failure);
    // Engine verdicts are not recomputed in mock mode; the corrected extraction is echoed back.
    return freshResult({
      lang: request.lang,
      extraction: structuredClone(request.extraction),
      reports: structuredClone(reportsFor(request.profiles)),
    });
  },
  async ask(request, options) {
    const failure = mockErrorFromUrl();
    await delay(MOCK_DELAYS_MS.ask, options?.signal);
    throwIfMockError(failure);
    return { ...structuredClone(fixtureAsk), lang: request.lang };
  },
  async parseProfile(_request, options) {
    const failure = mockErrorFromUrl();
    await delay(MOCK_DELAYS_MS.parseProfile, options?.signal);
    throwIfMockError(failure);
    return structuredClone(fixtureProfileParse);
  },
  async explain(_request, options) {
    const failure = mockErrorFromUrl();
    await delay(MOCK_DELAYS_MS.explain, options?.signal);
    throwIfMockError(failure);
    return structuredClone(fixtureExplain);
  },
};
