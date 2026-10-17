import { ArrowRight, Camera, Columns2, X } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { DifferencesList } from "../components/compare/DifferencesList";
import { FamilyCompare } from "../components/compare/FamilyCompare";
import { NutritionCompare } from "../components/compare/NutritionCompare";
import { RouteFallback } from "../components/layout/RouteFallback";
import { useCatalog } from "../components/profiles/useCatalog";
import { Button, ButtonLink } from "../components/ui/Button";
import { ErrorNotice } from "../components/ui/ErrorNotice";
import { Spinner } from "../components/ui/Spinner";
import { AnalysingView } from "../components/verdict/AnalysingView";
import { differences, familyComparison, nutritionComparison } from "../lib/compare";
import type { ScanResult } from "../shared/contract";
import { useProfilesStore } from "../store/profiles";
import { useScanStore, type Panel } from "../store/scan";
import { useUiStore } from "../store/ui";

const SCAN_B = "/scan?compare=1";

interface Product {
  result: ScanResult;
  panels: Panel[];
  /** The scan the result screen shows (the other one is the store's `pinned`). */
  current: boolean;
}

function ProductCard({ product, letterKey, onOpen }: { product: Product; letterKey: string; onOpen: () => void }) {
  const { t } = useTranslation();
  const photo = product.panels[0]?.url;
  return (
    <article className="card flex min-w-0 flex-col gap-3 p-3">
      <div className="flex items-center gap-3">
        <span className="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-surface-2">
          {photo ? <img src={photo} alt="" className="size-full object-cover" /> : <Columns2 className="size-5 text-text-dim" aria-hidden="true" />}
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-text-dim">{t(letterKey)}</p>
          <h2 className="line-clamp-2 text-sm font-bold">{product.result.extraction.product_name ?? t("result.unnamedProduct")}</h2>
        </div>
      </div>
      <Button variant="secondary" className="w-full !px-3" onClick={onOpen} icon={<ArrowRight className="size-4" aria-hidden="true" />}>
        {t("compare.openResult")}
      </Button>
    </article>
  );
}

function CompareView({ a, b }: { a: Product; b: Product }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const lang = useUiStore((state) => state.lang);
  const { scanProfiles, isDemo, status, recheckError, recheck, pinned, pinnedStatus, pinnedError, recheckPinned, swapCompare, stopCompare } =
    useScanStore();
  const { profiles: savedProfiles, hydrated: profilesHydrated } = useProfilesStore();
  const catalog = useCatalog();

  // Like the result screen, a real scan follows the saved family (if one is saved; otherwise A's family is kept).
  useEffect(() => {
    if (isDemo || !profilesHydrated || savedProfiles.length === 0 || status !== "done" || recheckError) return;
    if (JSON.stringify(savedProfiles) !== JSON.stringify(scanProfiles)) void recheck(lang, savedProfiles);
  }, [isDemo, profilesHydrated, status, recheckError, savedProfiles, scanProfiles, recheck, lang]);

  // Both products are checked for one family: the set-aside product follows the current scan's family.
  useEffect(() => {
    if (!pinned || status !== "done" || pinnedStatus !== "idle" || pinnedError) return;
    if (JSON.stringify(pinned.scanProfiles) !== JSON.stringify(scanProfiles)) void recheckPinned(scanProfiles, lang);
  }, [pinned, status, pinnedStatus, pinnedError, scanProfiles, recheckPinned, lang]);

  const relevant = useMemo(() => {
    const keys = new Set(scanProfiles.flatMap((profile) => profile.restrictions.map((restriction) => restriction.key)));
    if (keys.size === 0 || catalog.status !== "ready") return null;
    return new Set(catalog.items.filter((item) => keys.has(item.key)).flatMap((item) => item.categories));
  }, [scanProfiles, catalog.status, catalog.items]);

  const family = useMemo(() => familyComparison(a.result, b.result, scanProfiles), [a.result, b.result, scanProfiles]);
  const nutrition = useMemo(() => nutritionComparison(a.result, b.result), [a.result, b.result]);
  const diffs = useMemo(() => differences(a.result, b.result, relevant), [a.result, b.result, relevant]);

  async function open(product: Product) {
    if (!product.current) await swapCompare();
    navigate("/result");
  }

  return (
    <div data-page="compare" className="page-gutter mx-auto max-w-page space-y-6 pb-24 pt-4 lg:pt-8">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-2xl font-bold sm:text-3xl">{t("compare.title")}</h1>
        {(status === "rechecking" || pinnedStatus === "rechecking") && (
          <span role="status" className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-dim">
            <Spinner className="size-3.5" />
            {pinnedStatus === "rechecking" ? t("compare.rechecking") : t("result.rechecking")}
          </span>
        )}
        <Button
          variant="ghost"
          className="ml-auto"
          onClick={() => void stopCompare().then(() => navigate("/result"))}
          icon={<X className="size-4" aria-hidden="true" />}
        >
          {t("compare.stop")}
        </Button>
      </div>

      {pinnedError && (
        <p role="alert" className="rounded-xl bg-conflict/10 p-3 text-sm">
          {t("compare.recheckFailed")}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <ProductCard product={a} letterKey="compare.productA" onOpen={() => void open(a)} />
        <ProductCard product={b} letterKey="compare.productB" onOpen={() => void open(b)} />
      </div>

      <section aria-labelledby="compare-family" className="space-y-3">
        <h2 id="compare-family" className="text-lg font-bold">{t("compare.family.title")}</h2>
        <FamilyCompare rows={family} />
      </section>

      <section aria-labelledby="compare-diff" className="space-y-3">
        <h2 id="compare-diff" className="text-lg font-bold">{t("compare.diff.title")}</h2>
        <DifferencesList items={diffs} per100Unit={nutrition.unitA} />
      </section>

      <section aria-labelledby="compare-nutrition" className="space-y-3">
        <h2 id="compare-nutrition" className="text-lg font-bold">{t("result.tabs.nutrition")}</h2>
        <NutritionCompare comparison={nutrition} />
      </section>

      <p className="text-sm text-text-dim">{t("compare.note")}</p>
    </div>
  );
}

function Notice({ title, body, action }: { title: string; body: string; action: React.ReactNode }) {
  return (
    <div className="page-gutter mx-auto max-w-xl py-16 text-center">
      <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-beam">
        <Columns2 className="size-7" aria-hidden="true" />
      </span>
      <h1 className="mt-5 text-3xl font-bold">{title}</h1>
      <p className="mt-3 text-text-dim">{body}</p>
      <div className="mt-7 flex justify-center">{action}</div>
    </div>
  );
}

/** Two products side by side: product A was set aside from the result screen, product B is the latest scan. */
export default function Compare() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const lang = useUiStore((state) => state.lang);
  const { status, result, panels, error, hydrated, attemptProfiles, analyse, cancel, pinned, swapped } = useScanStore();

  if (!hydrated) return <RouteFallback />;
  if (!pinned) {
    return (
      <Notice
        title={t("compare.empty.title")}
        body={t("compare.empty.body")}
        action={
          <ButtonLink to="/scan" icon={<Camera className="size-4" aria-hidden="true" />}>
            {t("landing.cta.scan")}
          </ButtonLink>
        }
      />
    );
  }
  if (status === "analysing") {
    return (
      <AnalysingView
        panels={panels}
        profileCount={attemptProfiles.length}
        onCancel={() => {
          cancel();
          navigate(SCAN_B);
        }}
      />
    );
  }
  if (status === "error" && error) {
    return (
      <div className="page-gutter mx-auto max-w-xl py-10">
        <ErrorNotice
          error={error}
          title={t("result.error.title")}
          onRetry={panels.length > 0 ? () => void analyse({ profiles: attemptProfiles, lang }) : undefined}
          actions={
            <ButtonLink to={SCAN_B} variant="secondary">
              {t("analysing.editPhotos")}
            </ButtonLink>
          }
        />
      </div>
    );
  }
  const name = pinned.result.extraction.product_name ?? t("result.unnamedProduct");
  if (!result) {
    return (
      <Notice
        title={t("compare.scanSecond.title")}
        body={t("compare.scanSecond.body", { name })}
        action={
          <ButtonLink to={SCAN_B} icon={<Camera className="size-4" aria-hidden="true" />}>
            {t("compare.scanSecond.action")}
          </ButtonLink>
        }
      />
    );
  }
  const current: Product = { result, panels, current: true };
  const other: Product = { result: pinned.result, panels: pinned.panels, current: false };
  return swapped ? <CompareView a={current} b={other} /> : <CompareView a={other} b={current} />;
}
