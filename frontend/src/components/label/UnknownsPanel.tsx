import { useTranslation } from "react-i18next";
import { cropStyle, imageIndex } from "../../lib/boxMath";
import type { UnknownItem } from "../../shared/contract";
import type { Panel } from "../../store/scan";
import { useUiStore } from "../../store/ui";
import { Message } from "../ui/Message";
import { RetakeLink } from "./RetakeLink";

/** "What we couldn't read": each gap with a thumbnail of the area and a one-tap retake for that panel. */
export function UnknownsPanel({ unknowns, panels }: { unknowns: UnknownItem[]; panels: Panel[] }) {
  const { t } = useTranslation();
  const focusEvidence = useUiStore((state) => state.focusEvidence);

  if (unknowns.length === 0) {
    return <p className="card p-5 text-sm text-text-dim">{t("result.unknowns.empty")}</p>;
  }

  return (
    <ul className="space-y-3">
      {unknowns.map((unknown, index) => {
        const region = unknown.region?.box ? unknown.region : null;
        const panelIndex = region ? imageIndex(region.image_id) : 0;
        const panel = panels[panelIndex];
        return (
          <li key={`${unknown.section}:${index}`} className="card overflow-hidden">
            <div className="hatch flex gap-3 p-4 shadow-[inset_3px_0_0_var(--unknown)]">
              {region && region.box && panel && (
                <button
                  type="button"
                  onClick={() => focusEvidence(region, "unknown")}
                  aria-label={t("unknowns.region")}
                  className="h-14 w-28 shrink-0 rounded-lg bg-surface-2 bg-no-repeat shadow-[inset_0_0_0_1px_var(--unknown)]"
                  style={{ backgroundImage: `url(${panel.url})`, ...cropStyle(region.box) }}
                />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold">
                  <Message messageKey={unknown.message_key} />
                </p>
                {unknown.detail && <p className="mt-1 text-xs text-text-dim">{unknown.detail}</p>}
              </div>
            </div>
            {panels.length > 0 && (
              <div className="border-t border-line p-3">
                <RetakeLink imageId={region?.image_id ?? `img_${Math.min(panelIndex, panels.length - 1)}`} />
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
