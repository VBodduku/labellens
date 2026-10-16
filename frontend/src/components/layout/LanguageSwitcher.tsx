import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { LANGS } from "../../i18n/resources";
import type { Lang } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

/** Short labels are shown in each language's own script, never translated. */
const SHORT_LABELS: Record<Lang, string> = { en: "EN", hi: "हिं", te: "తె" };

export function LanguageSwitcher() {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const setLang = useUiStore((state) => state.setLang);

  return (
    <div role="radiogroup" aria-label={t("lang.label")} className="flex rounded-chip bg-surface-2 p-1">
      {LANGS.map((option) => {
        const selected = option === lang;
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={t(`lang.${option}`)}
            lang={option}
            onClick={() => setLang(option)}
            className={`relative min-h-9 min-w-9 rounded-chip px-2 text-[0.8rem] font-bold leading-none transition-colors duration-fast ${
              selected ? "text-text" : "text-text-dim hover:text-text"
            }`}
          >
            {selected && (
              <motion.span
                layoutId="lang-pill"
                className="absolute inset-0 rounded-chip bg-surface shadow-[inset_0_0_0_1px_var(--line)]"
                transition={{ type: "spring", stiffness: 500, damping: 38 }}
              />
            )}
            <span className="relative">{SHORT_LABELS[option]}</span>
          </button>
        );
      })}
    </div>
  );
}
