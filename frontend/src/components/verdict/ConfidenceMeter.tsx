import { useTranslation } from "react-i18next";

/** Subtle confidence bar (transform-scaled) with its value for screen readers and on hover. */
export function ConfidenceMeter({ value }: { value: number }) {
  const { t } = useTranslation();
  const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const label = t("result.confidence", { value: percent });
  return (
    <div className="flex items-center gap-2" title={label}>
      <div className="h-1 w-16 overflow-hidden rounded-full bg-line" aria-hidden="true">
        <div className="h-full origin-left rounded-full bg-text-dim" style={{ transform: `scaleX(${percent / 100})` }} />
      </div>
      <span className="text-[0.7rem] text-text-dim">{label}</span>
    </div>
  );
}
