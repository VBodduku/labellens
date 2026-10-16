import type { HealthResponse } from "../shared/contract";

/**
 * How the next scan will be read, from /api/health: the cloud AI reader, only the slower on-device reader
 * (which may fall back to basic reading), or basic text reading only. `null` = not known (no answer yet).
 */
export type ReaderStatus = "ai" | "local" | "basic";

export function readerStatus(health: HealthResponse | null): ReaderStatus | null {
  if (!health) return null;
  if (health.providers.gemini) return "ai";
  return health.providers.ollama ? "local" : "basic";
}
