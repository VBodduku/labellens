import type {
  AskResponse,
  ExplainResponse,
  HealthResponse,
  ProfileParseResponse,
  RestrictionCatalogItem,
  ScanResult,
} from "../shared/contract";
import { ApiError, parseErrorResponse, toApiError } from "./errors";
import type { CallOptions, LabelLensApi, ScanInput } from "./types";

export const SCAN_TIMEOUT_MS = 60_000;
export const DEFAULT_TIMEOUT_MS = 20_000;

interface RequestOptions extends CallOptions {
  method?: "GET" | "POST";
  json?: unknown;
  body?: FormData;
  timeoutMs?: number;
}

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  return typeof configured === "string" ? configured.replace(/\/+$/, "") : "";
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return null;
  }
}

/** fetch with a hard timeout, caller cancellation and typed ApiError failures. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const forwardAbort = () => controller.abort();
  if (options.signal?.aborted) controller.abort();
  options.signal?.addEventListener("abort", forwardAbort, { once: true });

  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    let body: BodyInit | undefined = options.body;
    if (options.json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(options.json);
    }
    const response = await fetch(`${apiBaseUrl()}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: controller.signal,
    });
    const payload = await readJson(response);
    if (!response.ok) throw parseErrorResponse(response.status, payload);
    if (payload === null) throw new ApiError("INTERNAL", "The server sent an empty response", { status: response.status });
    return payload as T;
  } catch (error) {
    if (timedOut) throw new ApiError("TIMEOUT", "The request took too long");
    throw toApiError(error);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", forwardAbort);
  }
}

export function buildScanForm(input: ScanInput): FormData {
  const form = new FormData();
  input.images.forEach((image, index) => {
    const extension = image.type === "image/png" ? "png" : image.type === "image/svg+xml" ? "svg" : "jpg";
    form.append("images", image, `panel_${index}.${extension}`);
  });
  form.append("profiles", JSON.stringify(input.profiles));
  form.append("lang", input.lang);
  if (input.panelHints) form.append("panel_hints", JSON.stringify(input.panelHints));
  return form;
}

export const realApi: LabelLensApi = {
  health: (options) => request<HealthResponse>("/api/health", options),
  catalog: (options) => request<RestrictionCatalogItem[]>("/api/catalog", options),
  scan: (input, options) =>
    request<ScanResult>("/api/scan", { ...options, method: "POST", body: buildScanForm(input), timeoutMs: SCAN_TIMEOUT_MS }),
  recheck: (body, options) => request<ScanResult>("/api/recheck", { ...options, method: "POST", json: body }),
  ask: (body, options) => request<AskResponse>("/api/ask", { ...options, method: "POST", json: body }),
  parseProfile: (body, options) =>
    request<ProfileParseResponse>("/api/profile/parse", { ...options, method: "POST", json: body }),
  explain: (body, options) => request<ExplainResponse>("/api/explain", { ...options, method: "POST", json: body }),
};
