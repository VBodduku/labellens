import { RotateCcw, X } from "lucide-react";
import { AnimatePresence, m } from "motion/react";
import { useTranslation } from "react-i18next";
import type { PanelHint } from "../../shared/contract";
import type { Panel } from "../../store/scan";

const HINTS: PanelHint[] = ["front", "back", "side"];

interface PanelTrayProps {
  panels: Panel[];
  retakeIndex: number | null;
  onRetake: (index: number | null) => void;
  onRemove: (index: number) => void;
  onHint: (index: number, hint: PanelHint) => void;
}

/** Up to three captured panels: label each (Front/Back/Side), retake one, or remove it. */
export function PanelTray({ panels, retakeIndex, onRetake, onRemove, onHint }: PanelTrayProps) {
  const { t } = useTranslation();
  return (
    <ul className="flex justify-center gap-2.5">
      <AnimatePresence initial={false}>
        {panels.map((panel, index) => {
          const retaking = retakeIndex === index;
          return (
            <m.li
              key={panel.id}
              layout
              initial={{ opacity: 0, scale: 0.6, y: -40 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.6 }}
              transition={{ type: "spring", stiffness: 420, damping: 32 }}
              className={`w-[5.75rem] overflow-hidden rounded-xl bg-black/55 backdrop-blur-md ${
                retaking ? "ring-2 ring-[var(--beam)]" : "ring-1 ring-white/15"
              }`}
            >
              <div className="relative">
                <img src={panel.url} alt={t("scan.panelLabel", { n: index + 1 })} className="h-14 w-full object-cover" />
                <button
                  type="button"
                  onClick={() => onRemove(index)}
                  aria-label={t("scan.remove", { n: index + 1 })}
                  className="absolute right-0 top-0 flex size-11 items-start justify-end p-1"
                >
                  <span className="flex size-6 items-center justify-center rounded-full bg-black/70 text-white">
                    <X className="size-3.5" aria-hidden="true" />
                  </span>
                </button>
              </div>
              <div className="flex items-stretch">
                <label className="sr-only" htmlFor={`hint-${panel.id}`}>
                  {t("scan.panelLabel", { n: index + 1 })}
                </label>
                <select
                  id={`hint-${panel.id}`}
                  value={panel.hint}
                  onChange={(event) => onHint(index, event.target.value as PanelHint)}
                  className="min-h-11 min-w-0 flex-1 bg-transparent pl-2 text-xs font-semibold text-white"
                >
                  {panel.hint === "unknown" && <option value="unknown">{t("scan.panel.unknown")}</option>}
                  {HINTS.map((hint) => (
                    <option key={hint} value={hint} className="text-black">
                      {t(`scan.panel.${hint}`)}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => onRetake(retaking ? null : index)}
                  aria-label={t("scan.retake", { n: index + 1 })}
                  aria-pressed={retaking}
                  className={`flex min-h-11 w-9 items-center justify-center ${retaking ? "text-[var(--beam)]" : "text-white/80"}`}
                >
                  <RotateCcw className="size-4" aria-hidden="true" />
                </button>
              </div>
            </m.li>
          );
        })}
      </AnimatePresence>
    </ul>
  );
}
