import { Camera, ImagePlus, ScanText, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { RouteFallback } from "../components/layout/RouteFallback";
import { ScanBeam } from "../components/landing/ScanBeam";
import { useDemoLauncher } from "../components/landing/useDemoLauncher";
import { Button, ButtonLink } from "../components/ui/Button";
import { ErrorNotice } from "../components/ui/ErrorNotice";
import { Message } from "../components/ui/Message";
import { ProfileReportCard } from "../components/verdict/ProfileReportCard";
import { sortByStateWorstFirst } from "../lib/verdict";
import type { ScanResult } from "../shared/contract";
import { useProfilesStore } from "../store/profiles";
import { useScanStore, type Panel } from "../store/scan";
import { useUiStore } from "../store/ui";

function LabelPhoto({ panel, index, beam = false }: { panel: Panel; index: number; beam?: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="relative overflow-hidden rounded-card bg-surface-2 shadow-[inset_0_0_0_1px_var(--line)]">
      <img src={panel.url} alt={t("result.photoAlt", { n: index + 1 })} className="mx-auto max-h-[46svh] w-auto object-contain lg:max-h-[78svh]" />
      {beam && <ScanBeam overhang={false} />}
    </div>
  );
}

function Analysing({ panels, onCancel }: { panels: Panel[]; onCancel: () => void }) {
  const { t } = useTranslation();
  const first = panels[0];
  return (
    <div className="page-gutter mx-auto max-w-xl py-8" role="status" aria-live="polite">
      {first && <LabelPhoto panel={first} index={0} beam />}
      <p className="mt-6 text-center text-lg font-semibold">{t("result.loading")}</p>
      <div className="mt-4 flex justify-center">
        <Button variant="secondary" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
      </div>
    </div>
  );
}

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

function ResultView({ result, panels, isDemo }: { result: ScanResult; panels: Panel[]; isDemo: boolean }) {
  const { t } = useTranslation();
  const scanProfiles = useScanStore((state) => state.scanProfiles);
  const reports = sortByStateWorstFirst(result.reports, (report) => report.overall);

  return (
    <div className="page-gutter mx-auto max-w-page py-6 lg:py-10">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold sm:text-3xl">{result.extraction.product_name ?? t("result.unnamedProduct")}</h1>
        {isDemo && <span className="rounded-chip bg-surface-2 px-3 py-1 text-xs font-semibold text-beam">{t("result.demoBadge")}</span>}
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-10">
        <div className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          {panels.map((panel, index) => (
            <LabelPhoto key={panel.id} panel={panel} index={index} />
          ))}
        </div>
        <div className="space-y-4">
          {reports.length === 0 ? (
            <div className="card p-6">
              <h2 className="text-lg font-bold">{t("result.noProfiles.title")}</h2>
              <p className="mt-2 text-sm text-text-dim">{t("result.noProfiles.body")}</p>
              <ButtonLink to="/profiles" variant="secondary" className="mt-4" icon={<Users className="size-4" aria-hidden="true" />}>
                {t("result.noProfiles.action")}
              </ButtonLink>
            </div>
          ) : (
            reports.map((report) => (
              <ProfileReportCard
                key={report.profile_id}
                report={report}
                profile={scanProfiles.find((profile) => profile.profile_id === report.profile_id)}
              />
            ))
          )}
          <section aria-labelledby="unknowns-title" className="card p-5">
            <h2 id="unknowns-title" className="text-base font-bold">
              {t("result.unknowns.title")}
            </h2>
            {result.unknowns.length === 0 ? (
              <p className="mt-2 text-sm text-text-dim">{t("result.unknowns.empty")}</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {result.unknowns.map((unknown, index) => (
                  <li key={index} className="hatch rounded-xl p-3 text-sm shadow-[inset_0_0_0_1px_var(--unknown)]">
                    <Message messageKey={unknown.message_key} />
                    {unknown.detail && <span className="mt-1 block text-xs text-text-dim">{unknown.detail}</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

export default function Result() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { status, result, panels, error, isDemo, hydrated, analyse, cancel } = useScanStore();
  const profiles = useProfilesStore((state) => state.profiles);
  const lang = useUiStore((state) => state.lang);

  if (status === "analysing") {
    return (
      <Analysing
        panels={panels}
        onCancel={() => {
          cancel();
          navigate("/scan");
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
          actions={
            <>
              {panels.length > 0 && <Button onClick={() => void analyse({ profiles, lang })}>{t("common.retry")}</Button>}
              <ButtonLink to="/scan" variant="secondary">
                {t("scan.title")}
              </ButtonLink>
            </>
          }
        />
      </div>
    );
  }
  if (!result) return hydrated ? <EmptyResult /> : <RouteFallback />;
  return <ResultView result={result} panels={panels} isDemo={isDemo} />;
}
