import { useId } from "react";
import { useTranslation } from "react-i18next";
import type { Threshold } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { Message } from "../ui/Message";

function unitFor(nutrient: string): string {
  if (nutrient.endsWith("_mg")) return "mg";
  if (nutrient.endsWith("_kcal")) return "kcal";
  return "g";
}

/** Slider + number for a nutrient limit, starting from the catalog default and showing where it comes from. */
export function ThresholdControl({ threshold, onChange }: { threshold: Threshold; onChange: (next: Threshold) => void }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const id = useId();
  const unit = unitFor(threshold.nutrient);
  const large = threshold.max_value >= 100;
  const step = large ? 10 : 0.5;
  const max = Math.max(large ? 2000 : 50, Math.ceil(threshold.max_value * 2));

  function update(value: number) {
    if (Number.isFinite(value) && value >= 0) onChange({ ...threshold, max_value: value });
  }

  return (
    <div className="mt-3 rounded-xl bg-surface-2 p-3">
      <label htmlFor={id} className="block text-xs font-semibold">
        <Message messageKey="profiles.threshold" params={{ nutrient: threshold.nutrient, basis: threshold.basis }} lang={lang} />
      </label>
      <div className="mt-2 flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={max}
          step={step}
          value={threshold.max_value}
          onChange={(event) => update(Number(event.target.value))}
          aria-label={t("profiles.thresholdSlider")}
          className="h-11 min-w-0 flex-1 accent-[var(--beam)]"
        />
        <div className="flex items-center gap-1">
          <input
            id={id}
            type="number"
            inputMode="decimal"
            min={0}
            step={step}
            value={threshold.max_value}
            onChange={(event) => update(Number(event.target.value))}
            className="min-h-11 w-20 rounded-lg bg-surface px-2 text-right text-sm font-semibold tabular-nums shadow-[inset_0_0_0_1px_var(--line)]"
          />
          <span className="text-xs text-text-dim">{unit}</span>
        </div>
      </div>
      {threshold.source_note && <p className="mt-1 text-[0.72rem] text-text-dim">{t("profiles.thresholdSource", { note: threshold.source_note })}</p>}
    </div>
  );
}
