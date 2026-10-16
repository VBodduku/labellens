import { useTranslation } from "react-i18next";
import type { Panel } from "../../store/scan";

/** Thumbnails to switch between scanned panels (shown only when there is more than one). */
export function PanelSwitcher({ panels, active, onChange }: { panels: Panel[]; active: number; onChange: (index: number) => void }) {
  const { t } = useTranslation();
  if (panels.length < 2) return null;
  return (
    <div role="tablist" aria-label={t("result.viewer.label")} className="flex gap-2">
      {panels.map((panel, index) => (
        <button
          key={panel.id}
          type="button"
          role="tab"
          aria-selected={index === active}
          aria-label={t("result.viewer.panel", { n: index + 1 })}
          onClick={() => onChange(index)}
          className={`size-11 overflow-hidden rounded-lg bg-surface-2 transition-[box-shadow] duration-fast ${
            index === active ? "shadow-[0_0_0_2px_var(--beam)]" : "opacity-70 shadow-[inset_0_0_0_1px_var(--line)]"
          }`}
        >
          <img src={panel.url} alt="" className="size-full object-cover" />
        </button>
      ))}
    </div>
  );
}
