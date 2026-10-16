import { afterEach, describe, expect, it, vi } from "vitest";
import { buildScanForm, request } from "./client";
import { parseErrorResponse, toApiError } from "./errors";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("real API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(200, { status: "ok" })));
    await expect(request("/api/health")).resolves.toEqual({ status: "ok" });
  });

  it("turns an ErrorResponse into a typed ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(429, { error_code: "RATE_LIMITED", message: "slow down", retry_after_s: 12 })),
    );
    await expect(request("/api/scan", { method: "POST" })).rejects.toMatchObject({
      code: "RATE_LIMITED",
      status: 429,
      retryAfterS: 12,
      message: "slow down",
    });
  });

  it("maps a hung request to TIMEOUT", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        (_url: string, init: RequestInit) =>
          new Promise((_resolve, reject) => {
            init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
          }),
      ),
    );
    const pending = request("/api/health", { timeoutMs: 1000 });
    const assertion = expect(pending).rejects.toMatchObject({ code: "TIMEOUT" });
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });

  it("maps a failed fetch to NETWORK", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(request("/api/health")).rejects.toMatchObject({ code: "NETWORK" });
  });

  it("builds the scan form with images in order and JSON fields", () => {
    const form = buildScanForm({
      images: [new Blob(["a"], { type: "image/jpeg" }), new Blob(["b"], { type: "image/png" })],
      profiles: [],
      lang: "hi",
      panelHints: ["back", "side"],
    });
    const images = form.getAll("images") as File[];
    expect(images.map((file) => file.name)).toEqual(["panel_0.jpg", "panel_1.png"]);
    expect(form.get("profiles")).toBe("[]");
    expect(form.get("lang")).toBe("hi");
    expect(form.get("panel_hints")).toBe('["back","side"]');
  });
});

describe("error parsing", () => {
  it("falls back to sensible codes for unknown or malformed bodies", () => {
    expect(parseErrorResponse(500, "<html>").code).toBe("INTERNAL");
    expect(parseErrorResponse(429, null).code).toBe("RATE_LIMITED");
    expect(parseErrorResponse(422, {}).code).toBe("VALIDATION");
    expect(parseErrorResponse(400, { error_code: "WHO_KNOWS", message: "x" }).code).toBe("INTERNAL");
  });

  it("recognises cancellations", () => {
    expect(toApiError(new DOMException("x", "AbortError")).code).toBe("ABORTED");
  });
});
