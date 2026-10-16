import { ImagePlus, ScanText, Trash2 } from "lucide-react";
import { useRef, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { IconButton } from "../components/ui/IconButton";
import type { PanelHint } from "../shared/contract";
import { useProfilesStore } from "../store/profiles";
import { MAX_PANELS, useScanStore } from "../store/scan";
import { useUiStore } from "../store/ui";

const HINTS: PanelHint[] = ["front", "back", "side"];

/** Photo upload flow (the live camera with quality guidance replaces the picker in Phase 2). */
export default function Scan() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { search } = useLocation();
  const input = useRef<HTMLInputElement>(null);
  const { panels: storedPanels, isDemo, addPanel, removePanel, setPanelHint, analyse } = useScanStore();
  const profiles = useProfilesStore((state) => state.profiles);
  const lang = useUiStore((state) => state.lang);
  const panels = isDemo ? [] : storedPanels;
  const full = panels.length >= MAX_PANELS;

  function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []).slice(0, MAX_PANELS - panels.length);
    files.forEach((file, index) => addPanel(file, panels.length + index === 0 ? "back" : "side"));
    event.target.value = "";
  }

  function onAnalyse() {
    void analyse({ profiles, lang });
    // Keep the query string so dev switches such as ?mockError=RATE_LIMITED survive into the result view.
    navigate({ pathname: "/result", search });
  }

  return (
    <div className="page-gutter mx-auto max-w-2xl py-8 lg:py-12">
      <h1 className="text-3xl font-bold">{t("scan.title")}</h1>
      <p className="mt-2 text-text-dim">{t("scan.subtitle")}</p>

      <input
        ref={input}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={onFiles}
      />

      {panels.length > 0 && (
        <ul className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {panels.map((panel, index) => (
            <li key={panel.id} className="card overflow-hidden">
              <img src={panel.url} alt={t("scan.panelLabel", { n: index + 1 })} className="aspect-[3/4] w-full object-cover" />
              <div className="flex items-center gap-1 p-2">
                <label className="sr-only" htmlFor={`hint-${panel.id}`}>
                  {t("scan.panelLabel", { n: index + 1 })}
                </label>
                <select
                  id={`hint-${panel.id}`}
                  value={panel.hint}
                  onChange={(event) => setPanelHint(index, event.target.value as PanelHint)}
                  className="min-h-11 min-w-0 flex-1 rounded-lg bg-surface-2 px-2 text-sm font-semibold text-text"
                >
                  {panel.hint === "unknown" && <option value="unknown">{t("scan.panel.unknown")}</option>}
                  {HINTS.map((hint) => (
                    <option key={hint} value={hint}>
                      {t(`scan.panel.${hint}`)}
                    </option>
                  ))}
                </select>
                <IconButton label={t("scan.remove", { n: index + 1 })} onClick={() => removePanel(index)}>
                  <Trash2 className="size-5" aria-hidden="true" />
                </IconButton>
              </div>
            </li>
          ))}
        </ul>
      )}

      {full ? (
        <p className="mt-4 text-sm text-text-dim">{t("scan.limit")}</p>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="mt-6 flex min-h-36 w-full flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed border-line bg-surface p-6 text-center transition-colors duration-fast hover:border-beam"
        >
          <span className="flex size-12 items-center justify-center rounded-2xl bg-surface-2 text-beam">
            <ImagePlus className="size-6" aria-hidden="true" />
          </span>
          <span className="font-semibold">{panels.length === 0 ? t("scan.choose") : t("scan.addMore")}</span>
          <span className="text-sm text-text-dim">{t("scan.tip")}</span>
        </button>
      )}

      {profiles.length === 0 && <p className="mt-4 rounded-xl bg-surface-2 p-4 text-sm text-text-dim">{t("scan.noProfiles")}</p>}

      <Button
        size="lg"
        className="mt-6 w-full sm:w-auto"
        disabled={panels.length === 0}
        onClick={onAnalyse}
        icon={<ScanText className="size-5" aria-hidden="true" />}
      >
        {t("scan.analyse")}
      </Button>
    </div>
  );
}
