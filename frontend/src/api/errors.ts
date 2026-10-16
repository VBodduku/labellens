import type { ErrorResponse } from "../shared/contract";

/** Error codes the backend may send (master spec §6) plus client-side failures. */
export const SERVER_ERROR_CODES = [
  "BAD_IMAGE",
  "TOO_MANY_IMAGES",
  "RATE_LIMITED",
  "LLM_UNAVAILABLE",
  "VALIDATION",
  "INTERNAL",
] as const;
export const CLIENT_ERROR_CODES = ["NETWORK", "TIMEOUT", "ABORTED"] as const;

export type ServerErrorCode = (typeof SERVER_ERROR_CODES)[number];
export type ClientErrorCode = (typeof CLIENT_ERROR_CODES)[number];
export type ApiErrorCode = ServerErrorCode | ClientErrorCode;

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  readonly status: number | null;
  readonly retryAfterS: number | null;

  constructor(code: ApiErrorCode, message: string, options: { status?: number | null; retryAfterS?: number | null } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = options.status ?? null;
    this.retryAfterS = options.retryAfterS ?? null;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

export function isServerErrorCode(value: unknown): value is ServerErrorCode {
  return typeof value === "string" && (SERVER_ERROR_CODES as readonly string[]).includes(value);
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null) return false;
  const record = value as Record<string, unknown>;
  return typeof record.error_code === "string" && typeof record.message === "string";
}

/** Builds an ApiError from an HTTP status and a (possibly malformed) JSON body. */
export function parseErrorResponse(status: number, body: unknown): ApiError {
  if (isErrorResponse(body)) {
    const code = isServerErrorCode(body.error_code) ? body.error_code : status === 429 ? "RATE_LIMITED" : "INTERNAL";
    return new ApiError(code, body.message, { status, retryAfterS: body.retry_after_s ?? null });
  }
  if (status === 429) return new ApiError("RATE_LIMITED", "Too many requests", { status });
  if (status === 422 || status === 400) return new ApiError("VALIDATION", "The request was not accepted", { status });
  return new ApiError("INTERNAL", `Request failed with status ${status}`, { status });
}

/** Normalises anything thrown during a request into an ApiError. */
export function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiError("ABORTED", "The request was cancelled");
  }
  if (error instanceof DOMException && error.name === "TimeoutError") {
    return new ApiError("TIMEOUT", "The request took too long");
  }
  return new ApiError("NETWORK", error instanceof Error ? error.message : "Network error");
}

/** i18n key for the friendly, specific message shown for each error code. */
export function errorMessageKey(code: ApiErrorCode): string {
  return `errors.${code}`;
}
