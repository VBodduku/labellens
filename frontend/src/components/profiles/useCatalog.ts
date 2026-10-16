import { useCallback, useEffect, useState } from "react";
import { api, ApiError, isApiError } from "../../api";
import type { RestrictionCatalogItem } from "../../shared/contract";

type CatalogState =
  | { status: "loading"; items: RestrictionCatalogItem[]; error: null }
  | { status: "ready"; items: RestrictionCatalogItem[]; error: null }
  | { status: "error"; items: RestrictionCatalogItem[]; error: ApiError };

let cached: RestrictionCatalogItem[] | null = null;

/** The engine's restriction catalog (loaded once per session, with retry on failure). */
export function useCatalog() {
  const [state, setState] = useState<CatalogState>(() =>
    cached ? { status: "ready", items: cached, error: null } : { status: "loading", items: [], error: null },
  );

  const load = useCallback(async () => {
    setState({ status: "loading", items: [], error: null });
    try {
      cached = await api.catalog();
      setState({ status: "ready", items: cached, error: null });
    } catch (error) {
      setState({ status: "error", items: [], error: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
    }
  }, []);

  useEffect(() => {
    if (!cached) void load();
  }, [load]);

  return { ...state, retry: load };
}
