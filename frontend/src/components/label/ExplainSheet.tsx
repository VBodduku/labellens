import { BookOpen, Sparkles, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, isApiError } from "../../api";
import type { ExplainResponse, Lang } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { Button } from "../ui/Button";
import { ErrorNotice } from "../ui/ErrorNotice";
import { Sheet } from "../ui/Sheet";
import { Skeleton } from "../ui/Skeleton";

const cache = new Map<string, ExplainResponse>();
const cacheKey = (term: string, lang: Lang) => `${lang}:${term.toLowerCase()}`;

type ExplainState = { status: "loading" } | { status: "done"; data: ExplainResponse } | { status: "error"; error: ApiError };

/** What an ingredient is — from our knowledge base, or an AI explanation clearly marked as such. */
export function ExplainSheet({ term, onClose }: { term: string | null; onClose: () => void }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const [state, setState] = useState<ExplainState>({ status: "loading" });

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!term) return;
      const cached = cache.get(cacheKey(term, lang));
      if (cached) {
        setState({ status: "done", data: cached });
        return;
      }
      setState({ status: "loading" });
      try {
        const data = await api.explain({ term, lang }, { signal });
        cache.set(cacheKey(term, lang), data);
        setState({ status: "done", data });
      } catch (error) {
        if (isApiError(error) && error.code === "ABORTED") return;
        setState({ status: "error", error: isApiError(error) ? error : new ApiError("INTERNAL", String(error)) });
      }
    },
    [term, lang],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return (
    <Sheet open={term !== null} title={term ?? ""} onClose={onClose}>
      {state.status === "loading" && (
        <div role="status" className="space-y-2">
          <span className="sr-only">{t("common.loading")}</span>
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      )}
      {state.status === "error" && <ErrorNotice error={state.error} actions={<Button onClick={() => void load()}>{t("common.retry")}</Button>} />}
      {state.status === "done" && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 lang="" className="text-xl font-bold">
              {state.data.display_name}
            </h3>
            {state.data.source === "kb" ? (
              <span className="inline-flex items-center gap-1 rounded-chip bg-not-listed/15 px-2.5 py-1 text-xs font-semibold text-not-listed">
                <BookOpen className="size-3.5" aria-hidden="true" />
                {t("explain.source.kb")}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-chip bg-possible/15 px-2.5 py-1 text-xs font-semibold text-possible">
                <Sparkles className="size-3.5" aria-hidden="true" />
                {t("explain.source.llm")}
              </span>
            )}
          </div>
          <p className="leading-relaxed">{state.data.description}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-text-dim">{t("explain.origin")}</dt>
            <dd>{t(`ingredients.origin.${state.data.origin}`)}</dd>
            {state.data.categories.length > 0 && (
              <>
                <dt className="text-text-dim">{t("explain.countsAs")}</dt>
                <dd className="flex flex-wrap gap-1">
                  {state.data.categories.map((category) => (
                    <span key={category} className="rounded-chip bg-surface-2 px-2 py-0.5 text-xs">
                      {t(`categories.${category}`)}
                    </span>
                  ))}
                </dd>
              </>
            )}
          </dl>
          {state.data.caution && (
            <p className="flex gap-2 rounded-xl bg-possible/10 p-3 text-sm shadow-[inset_0_0_0_1px_var(--possible)]">
              <TriangleAlert className="mt-0.5 size-4 shrink-0 text-possible" aria-hidden="true" />
              {state.data.caution}
            </p>
          )}
        </div>
      )}
    </Sheet>
  );
}
