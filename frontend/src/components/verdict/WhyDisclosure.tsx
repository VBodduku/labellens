import { ChevronDown } from "lucide-react";
import { AnimatePresence, m } from "motion/react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Match } from "../../shared/contract";

/** "Why?" — every signal the engine used, with where it came from (AI interpretations flagged for checking). */
export function WhyDisclosure({ matches }: { matches: Match[] }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <div className="mt-3">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
        className="-ml-2 inline-flex min-h-9 items-center gap-1 rounded-chip px-2 text-xs font-semibold text-text-dim hover:text-text"
      >
        {t("result.why")}
        <ChevronDown className={`size-3.5 transition-transform duration-fast ${open ? "rotate-180" : ""}`} aria-hidden="true" />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <m.div
            id={panelId}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }}
          >
            {matches.length === 0 ? (
              <p className="mt-1 text-xs leading-relaxed text-text-dim">{t("result.why.empty")}</p>
            ) : (
              <ul className="mt-1 space-y-2">
                {matches.map((match, index) => (
                  <li key={`${match.term}:${match.source}:${index}`} className="text-xs leading-relaxed">
                    <span lang="" className="evidence-text text-text">
                      {match.term}
                    </span>
                    {match.category && <span className="text-text-dim"> → {t(`categories.${match.category}`)}</span>}
                    <span className={`block ${match.source === "llm_interpretation" ? "font-semibold text-possible" : "text-text-dim"}`}>
                      {t(`why.source.${match.source}`)}
                    </span>
                    {match.note && <span className="block text-text-dim">{match.note}</span>}
                  </li>
                ))}
              </ul>
            )}
          </m.div>
        )}
      </AnimatePresence>
    </div>
  );
}
