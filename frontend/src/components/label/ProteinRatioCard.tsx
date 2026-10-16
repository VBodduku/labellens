import { CircleDashed } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatNumber } from "../../lib/format";
import { BANDS, NO_PROTEIN_COLOR, proteinRatio } from "../../lib/proteinRatio";
import type { NutritionAnalysis } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

/** Scale segments from the left (least protein for the calories) to the right (most). */
const SEGMENTS = [...BANDS].reverse();

function Dot({ color }: { color: string }) {
  return (
    <span
      className="size-3.5 shrink-0 rounded-full shadow-[0_0_0_1.5px_var(--line)]"
      style={{ backgroundColor: color }}
      aria-hidden="true"
    />
  );
}

/** Calories per gram of protein, rated in six bands from "Very poor" (red) to "Excellent" (green). */
export function ProteinRatioCard({ analysis }: { analysis: NutritionAnalysis | null | undefined }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const ratio = proteinRatio(analysis);
  const unit = analysis?.per_100_unit ?? "g";
  const title = (
    <h2 id="protein-ratio-title" className="text-sm font-semibold text-text-dim">
      {t("nutrition.proteinRatio.title")}
    </h2>
  );

  if (ratio.kind === "unavailable") {
    const key = ratio.reason === "no_energy" ? "noEnergy" : ratio.reason;
    return (
      <section className="card p-4" aria-labelledby="protein-ratio-title">
        {title}
        <p className="mt-1.5 flex items-start gap-2 text-sm text-text-dim">
          <CircleDashed className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {t(`nutrition.proteinRatio.${key}`)}
        </p>
      </section>
    );
  }

  const energy = formatNumber(ratio.energy, lang);
  if (ratio.kind === "no_protein") {
    return (
      <section className="card p-4" aria-labelledby="protein-ratio-title">
        {title}
        <p className="mt-2 flex items-center gap-2 text-xl font-bold">
          <Dot color={NO_PROTEIN_COLOR} />
          {t("nutrition.proteinRatio.band.none")}
        </p>
        <p className="mt-1 text-sm">{t("nutrition.proteinRatio.note.none")}</p>
        <p className="mt-3 text-xs text-text-dim">{t("nutrition.proteinRatio.noProtein", { energy, unit })}</p>
      </section>
    );
  }

  const rating = t(`nutrition.proteinRatio.band.${ratio.band}`);
  return (
    <section className="card p-4" aria-labelledby="protein-ratio-title">
      {title}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-2 text-2xl font-bold tabular-nums">
          <Dot color={ratio.color} />
          {t("nutrition.proteinRatio.value", { value: formatNumber(Math.round(ratio.kcalPerGram * 10) / 10, lang) })}
        </span>
        <span className="rounded-chip px-2.5 py-0.5 text-sm font-bold" style={{ boxShadow: `inset 0 0 0 1.5px ${ratio.color}` }}>
          {rating}
        </span>
      </div>
      <p className="mt-1 text-sm">{t(`nutrition.proteinRatio.note.${ratio.band}`)}</p>

      <div role="img" aria-label={rating} className="relative mt-4">
        <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full">
          {SEGMENTS.map((segment) => (
            <span key={segment.band} className="flex-1" style={{ backgroundColor: segment.color }} />
          ))}
        </div>
        <span
          className="absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg shadow-[0_0_0_1px_var(--text)]"
          style={{ left: `${ratio.position}%`, backgroundColor: ratio.color }}
          aria-hidden="true"
        />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-text-dim" aria-hidden="true">
        <span>{t("nutrition.proteinRatio.scaleLow")}</span>
        <span>{t("nutrition.proteinRatio.scaleHigh")}</span>
      </div>

      <p className="mt-3 text-xs text-text-dim">
        {t("nutrition.proteinRatio.basis", { energy, protein: formatNumber(ratio.protein, lang), unit })}
      </p>
    </section>
  );
}
