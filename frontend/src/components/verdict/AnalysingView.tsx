import { AnimatePresence, m } from "motion/react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Panel } from "../../store/scan";
import { ScanBeam } from "../landing/ScanBeam";
import { Button } from "../ui/Button";
import { stageAt } from "../../lib/analysingStages";

export function AnalysingView({ panels, profileCount, onCancel }: { panels: Panel[]; profileCount: number; onCancel: () => void }) {
  const { t } = useTranslation();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const started = performance.now();
    const timer = window.setInterval(() => setElapsed(performance.now() - started), 250);
    return () => window.clearInterval(timer);
  }, []);

  const stage = stageAt(elapsed, profileCount);
  const first = panels[0];

  return (
    <div className="page-gutter mx-auto flex max-w-md flex-col items-center py-8">
      {first && (
        <div className="relative w-full overflow-hidden rounded-card bg-surface-2 shadow-[inset_0_0_0_1px_var(--line)]">
          <img src={first.url} alt={t("result.photoAlt", { n: 1 })} className="mx-auto max-h-[52svh] w-auto object-contain opacity-80" />
          <ScanBeam overhang={false} />
        </div>
      )}
      {panels.length > 1 && (
        <div className="mt-3 flex gap-2" aria-hidden="true">
          {panels.slice(1).map((panel) => (
            <img key={panel.id} src={panel.url} alt="" className="size-12 rounded-lg object-cover opacity-70" />
          ))}
        </div>
      )}
      <div role="status" aria-live="polite" className="mt-6 min-h-8 text-center">
        <AnimatePresence mode="wait" initial={false}>
          <m.p
            key={stage}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.26 }}
            className="text-lg font-semibold"
          >
            {stage === "analysing.checking" ? t(stage, { count: profileCount }) : t(stage)}
          </m.p>
        </AnimatePresence>
      </div>
      <Button variant="secondary" className="mt-5" onClick={onCancel}>
        {t("common.cancel")}
      </Button>
    </div>
  );
}
