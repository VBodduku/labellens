import { AnimatePresence, m } from "motion/react";
import { useTranslation } from "react-i18next";
import type { LiveIssue } from "../../lib/quality";

/** One hint at a time — the most important issue — so the coaching is calm and readable. */
export function QualityHints({ issues, ready }: { issues: LiveIssue[] | null; ready: boolean }) {
  const { t } = useTranslation();
  const top = issues?.[0];
  const text = !ready ? null : top ? t(`quality.${top}`) : t("scan.hint.good");
  return (
    <div aria-live="polite" className="flex min-h-10 justify-center">
      <AnimatePresence mode="wait" initial={false}>
        {text && (
          <m.p
            key={text}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.16 }}
            className={`rounded-chip px-4 py-2 text-sm font-semibold backdrop-blur-md ${
              top ? "bg-black/60 text-white" : "bg-[color-mix(in_srgb,var(--beam)_85%,black)] text-[#06121a]"
            }`}
          >
            {text}
          </m.p>
        )}
      </AnimatePresence>
    </div>
  );
}
