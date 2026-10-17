import { Camera, Columns2, ImagePlus, ScanText, Users } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { AskBar } from "../components/ask/AskBar";
import { EvidenceViewer } from "../components/evidence/EvidenceViewer";
import type { OverlayItem } from "../components/evidence/EvidenceOverlay";
import type { EditTarget } from "../components/label/CorrectionEditor";
import { ExtractionMetaBadges } from "../components/label/ExtractionMetaBadges";
import { IngredientsList } from "../components/label/IngredientsList";
import { NutritionTable } from "../components/label/NutritionTable";
import { UnknownsPanel } from "../components/label/UnknownsPanel";
import { RouteFallback } from "../components/layout/RouteFallback";
import { useDemoLauncher } from "../components/landing/useDemoLauncher";
import { Button, ButtonLink } from "../components/ui/Button";
import { ErrorNotice } from "../components/ui/ErrorNotice";
import { Spinner } from "../components/ui/Spinner";
import { Tabs } from "../components/ui/Tabs";
import { panelId, tabId } from "../components/ui/tabIds";
import { AnalysingView } from "../components/verdict/AnalysingView";
import { ContradictionsPanel } from "../components/verdict/ContradictionsPanel";
import { FamilyStrip } from "../components/verdict/FamilyStrip";
import { FindingsSummary } from "../components/verdict/FindingsSummary";
import { ProfileVerdictCard } from "../components/verdict/ProfileVerdictCard";
import { makeCorrection } from "../lib/corrections";
import { useLatch } from "../lib/useLatch";
import { sortByStateWorstFirst } from "../lib/verdict";
import type { Box, ScanResult } from "../shared/contract";
import { useProfilesStore } from "../store/profiles";
import { useScanStore, type Panel } from "../store/scan";
import { useUiStore } from "../store/ui";

type TabKey = "verdicts" | "ingredients" | "nutrition" | "unknowns";

// Sheets load their code the first time they open (kept off the result screen's critical path).
const CorrectionEditor = lazy(() => import("../components/label/CorrectionEditor").then((module) => ({ default: module.CorrectionEditor })));
const ExplainSheet = lazy(() => import("../components/label/ExplainSheet").then((module) => ({ default: module.ExplainSheet })));
const TAB_PREFIX = "result";

function EmptyResult() {
  const { t } = useTranslation();
  const demo = useDemoLauncher();
  return (
    <div className="page-gutter mx-auto max-w-xl py-16 text-center">
      <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-surface-2 text-beam">
        <ImagePlus className="size-7" aria-hidden="true" />
      </span>
      <h1 className="mt-5 text-3xl font-bold">{t("result.empty.title")}</h1>
      <p className="mt-3 text-text-dim">{t("result.empty.body")}</p>
      <div className="mt-7 flex flex-wrap justify-center gap-3">
        <ButtonLink to="/scan" icon={<Camera className="size-4" aria-hidden="true" />}>
          {t("landing.cta.scan")}
        </ButtonLink>
        <Button
          variant="secondary"
          loading={demo.state === "loading"}
          onClick={() => void demo.launch()}
          icon={<ScanText className="size-4" aria-hidden="true" />}
        >
          {t("landing.cta.demo")}
        </Button>
      </div>
    </div>
  );
}

function ResultView({ result, panels }: { result: ScanResult; panels: Panel[] }) {
  const { t } = useTranslation();
  const { scanProfiles, isDemo, status, corrections, changedVerdicts, recheckError, addCorrection, recheck, checkContradiction, pinned, startCompare } =
    useScanStore();
  const navigate = useNavigate();
  const { profiles: savedProfiles, hydrated: profilesHydrated } = useProfilesStore();
  const { lang, selectedProfileId, selectProfile } = useUiStore();
  const [tab, setTab] = useState<TabKey>("nutrition");
  const [editing, setEditing] = useState<EditTarget | null>(null);
  const [explaining, setExplaining] = useState<string | null>(null);
  const editorMounted = useLatch(editing !== null);
  const contradictions = result.contradictions ?? [];
  const explainMounted = useLatch(explaining !== null);

  // Summaries are generated per language: after a switch, recheck (engine only) and show the template meanwhile.
  useEffect(() => {
    if (status === "done" && !recheckError && result.lang !== lang) void recheck(lang);
  }, [status, recheckError, result.lang, lang, recheck]);

  // Real scans follow the saved family: editing profiles rechecks the open result (the demo keeps its fixture family).
  useEffect(() => {
    if (isDemo || !profilesHydrated || status !== "done" || recheckError) return;
    if (JSON.stringify(savedProfiles) !== JSON.stringify(scanProfiles)) void recheck(lang, savedProfiles);
  }, [isDemo, profilesHydrated, status, recheckError, savedProfiles, scanProfiles, recheck, lang]);

  const reports = useMemo(() => sortByStateWorstFirst(result.reports, (report) => report.overall), [result.reports]);
  const selected = reports.find((report) => report.profile_id === selectedProfileId) ?? reports[0];

  useEffect(() => {
    const worst = reports[0];
    if (worst && !reports.some((report) => report.profile_id === selectedProfileId)) selectProfile(worst.profile_id);
  }, [reports, selectedProfileId, selectProfile]);

  const overlayItems = useMemo<OverlayItem[]>(() => {
    if (!selected) return [];
    return selected.results.flatMap((item) =>
      item.evidence.flatMap((evidence) =>
        evidence.box && evidence.status !== "unverified" ? [{ evidence: { ...evidence, box: evidence.box as Box }, state: item.state }] : [],
      ),
    );
  }, [selected]);

  function saveCorrection(fieldPath: string, value: string | number) {
    setEditing(null);
    void addCorrection(makeCorrection(result.extraction, fieldPath, value), lang);
  }

  const tabs = [
    { id: "nutrition" as const, label: t("result.tabs.nutrition") },
    { id: "ingredients" as const, label: t("result.tabs.ingredients") },
    { id: "verdicts" as const, label: t("result.tabs.verdicts") },
    { id: "unknowns" as const, label: t("result.tabs.unknowns"), badge: result.unknowns.length },
  ];

  return (
    <div data-page="result" className="page-gutter mx-auto max-w-page pb-32 pt-4 lg:pt-8">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="text-2xl font-bold sm:text-3xl">{result.extraction.product_name ?? t("result.unnamedProduct")}</h1>
        {isDemo && <span className="rounded-chip bg-surface-2 px-3 py-1 text-xs font-semibold text-beam">{t("result.demoBadge")}</span>}
        {status === "rechecking" && (
          <span role="status" className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-dim">
            <Spinner className="size-3.5" />
            {t("result.rechecking")}
          </span>
        )}
        <ButtonLink to="/scan" variant="ghost" className="ml-auto max-sm:hidden" icon={<Camera className="size-4" aria-hidden="true" />}>
          {t("result.scanAgain")}
        </ButtonLink>
      </div>
      <div className="mt-2">
        {pinned && pinned.result.scan_id !== result.scan_id ? (
          <ButtonLink to="/compare" variant="secondary" icon={<Columns2 className="size-4" aria-hidden="true" />}>
            {t("compare.open", { name: pinned.result.extraction.product_name ?? t("result.unnamedProduct") })}
          </ButtonLink>
        ) : (
          <Button
            variant="secondary"
            onClick={() => void startCompare().then(() => navigate("/scan?compare=1"))}
            icon={<Columns2 className="size-4" aria-hidden="true" />}
          >
            {t("compare.start")}
          </Button>
        )}
      </div>
      <div className="mt-2">
        <ExtractionMetaBadges meta={result.extraction.meta} />
      </div>
      {result.extraction.meta.provider === "ocr_only" && (
        <p role="status" className="hatch mt-3 rounded-xl p-3 text-sm shadow-[inset_0_0_0_1px_var(--unknown)]">
          {t("result.ocrOnly")}
        </p>
      )}
      {recheckError && (
        <div role="alert" className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-conflict/10 p-3 text-sm">
          <span className="flex-1">
            {t("result.recheckFailed")} {t(`errors.${recheckError.code}`)}
          </span>
          <Button variant="secondary" onClick={() => void recheck(lang)}>
            {t("common.retry")}
          </Button>
        </div>
      )}

      <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-8">
        <div className="sticky top-16 z-20 -mx-4 bg-bg/95 px-4 pb-2 pt-1 backdrop-blur lg:top-24 lg:mx-0 lg:h-[calc(100svh-7.5rem)] lg:self-start lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
          <EvidenceViewer panels={panels} images={result.extraction.images} items={overlayItems} className="lg:h-full" />
        </div>

        <div className="min-w-0 space-y-4">
          {reports.length > 0 && selected && (
            <FamilyStrip reports={reports} profiles={scanProfiles} selectedId={selected.profile_id} onSelect={selectProfile} />
          )}
          {selected && <FindingsSummary report={selected} contradictions={contradictions} />}
          <ContradictionsPanel
            contradictions={contradictions}
            extraction={result.extraction}
            profiles={scanProfiles}
            onCheck={(item) => void checkContradiction(item, lang)}
            onFix={setEditing}
          />
          <Tabs tabs={tabs} value={tab} onChange={setTab} label={t("result.tabs.label")} idPrefix={TAB_PREFIX} />
          <div role="tabpanel" id={panelId(TAB_PREFIX, tab)} aria-labelledby={tabId(TAB_PREFIX, tab)} tabIndex={0} className="focus-visible:outline-none">
            {tab === "verdicts" &&
              (selected ? (
                <ProfileVerdictCard
                  report={selected}
                  profile={scanProfiles.find((profile) => profile.profile_id === selected.profile_id)}
                  changed={changedVerdicts}
                />
              ) : (
                <div className="card p-6">
                  <h2 className="text-lg font-bold">{t("result.noProfiles.title")}</h2>
                  <p className="mt-2 text-sm text-text-dim">{t("result.noProfiles.body")}</p>
                  <ButtonLink to="/profiles" variant="secondary" className="mt-4" icon={<Users className="size-4" aria-hidden="true" />}>
                    {t("result.noProfiles.action")}
                  </ButtonLink>
                </div>
              ))}
            {tab === "ingredients" && (
              <IngredientsList result={result} corrections={corrections} onEdit={setEditing} onExplain={setExplaining} />
            )}
            {tab === "nutrition" && <NutritionTable result={result} onEdit={setEditing} />}
            {tab === "unknowns" && <UnknownsPanel unknowns={result.unknowns} panels={panels} />}
          </div>
        </div>
      </div>

      <Suspense fallback={null}>
        {editorMounted && <CorrectionEditor target={editing} onClose={() => setEditing(null)} onSave={saveCorrection} />}
        {explainMounted && <ExplainSheet term={explaining} onClose={() => setExplaining(null)} />}
      </Suspense>
      <AskBar result={result} profiles={scanProfiles} />
    </div>
  );
}

export default function Result() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { search } = useLocation();
  const { status, result, panels, error, hydrated, attemptProfiles, analyse, cancel } = useScanStore();
  const lang = useUiStore((state) => state.lang);

  if (status === "analysing") {
    return (
      <AnalysingView
        panels={panels}
        profileCount={attemptProfiles.length}
        onCancel={() => {
          cancel();
          navigate({ pathname: "/scan", search });
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
            <ButtonLink to={{ pathname: "/scan", search }} variant="secondary">
              {t("analysing.editPhotos")}
            </ButtonLink>
          }
        />
      </div>
    );
  }
  if (!result) return hydrated ? <EmptyResult /> : <RouteFallback />;
  return <ResultView result={result} panels={panels} />;
}
