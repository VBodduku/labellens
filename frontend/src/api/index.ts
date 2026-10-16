import type { LabelLensApi } from "./types";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

let implementation: Promise<LabelLensApi> | null = null;

/** Loads the mock (fixtures) or the real client on first use, so fixtures never ship in the main chunk. */
function load(): Promise<LabelLensApi> {
  implementation ??= USE_MOCKS
    ? import("./mock").then((module) => module.mockApi)
    : import("./client").then((module) => module.realApi);
  return implementation;
}

export const api: LabelLensApi = {
  health: async (options) => (await load()).health(options),
  catalog: async (options) => (await load()).catalog(options),
  scan: async (input, options) => (await load()).scan(input, options),
  recheck: async (request, options) => (await load()).recheck(request, options),
  ask: async (request, options) => (await load()).ask(request, options),
  parseProfile: async (request, options) => (await load()).parseProfile(request, options),
  explain: async (request, options) => (await load()).explain(request, options),
};

export const { health, catalog, scan, recheck, ask, parseProfile, explain } = api;
export { ApiError, isApiError, errorMessageKey, type ApiErrorCode } from "./errors";
export type { ScanInput, CallOptions, LabelLensApi } from "./types";
