import { LocateFixed, Pencil } from "lucide-react";
import { m } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { formatNumber } from "../../lib/format";
import { hasServingValues, nutritionRows, type NutritionBasisView } from "../../lib/nutritionView";
import type { ScanResult } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { IconButton } from "../ui/IconButton";
import { Message } from "../ui/Message";
import { ConsistencyBadge } from "./ConsistencyBadge";
import type { EditTarget } from "./CorrectionEditor";

/** Nutrition table with Per 100 g · Per serving · Whole pack, the calorie cross-check and editable values. */
export function NutritionTable({ result, onEdit }: { result: ScanResult; onEdit: (target: EditTarget) => void }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const focusEvidence = useUiStore((state) => state.focusEvidence);
  const [view, setView] = useState<NutritionBasisView>("per_100");
  const nutrition = result.extraction.nutrition;
  const analysis = result.nutrition_analysis;

  if (!nutrition || nutrition.rows.length === 0) {
    return <p className="card p-5 text-sm text-text-dim">{t("nutrition.empty")}</p>;
  }

  const options: NutritionBasisView[] = ["per_100"];
  if (hasServingValues(result)) options.push("per_serving");
  if (analysis) options.push("per_pack");
  const rows = nutritionRows(result, view);
  const unit = analysis?.per_100_unit ?? "g";

  return (
    <div className="space-y-4">
      <div role="radiogroup" aria-label={t("nutrition.basis.label")} className="flex rounded-chip bg-surface-2 p-1">
        {options.map((option) => (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={view === option}
            onClick={() => setView(option)}
            className={`relative min-h-10 flex-1 rounded-chip px-3 text-sm font-semibold touch:min-h-11 transition-colors duration-fast ${
              view === option ? "text-text" : "text-text-dim hover:text-text"
            }`}
          >
            {view === option && (
              <m.span
                layoutId="nutrition-basis"
                className="absolute inset-0 rounded-chip bg-surface shadow-[inset_0_0_0_1px_var(--line)]"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
            <span className="relative">{t(`nutrition.basis.${option}`, { unit })}</span>
          </button>
        ))}
      </div>

      {nutrition.serving_size && nutrition.servings_per_pack && (
        <p className="text-sm text-text-dim">
          {t("nutrition.serving", {
            size: formatNumber(nutrition.serving_size, lang),
            unit: nutrition.serving_unit ?? unit,
            servings: formatNumber(nutrition.servings_per_pack, lang),
          })}
        </p>
      )}

      {analysis && <ConsistencyBadge consistency={analysis.consistency} />}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="sr-only">
            <tr>
              <th scope="col">{t("nutrition.nutrient")}</th>
              <th scope="col">{t("nutrition.amount")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => {
              const locatable = row.evidence?.box && row.evidence.status !== "unverified" ? row.evidence : null;
              return (
                <tr key={row.key} className={row.suspect ? "bg-possible/10 shadow-[inset_3px_0_0_var(--possible)]" : undefined}>
                  <th scope="row" className="py-2.5 pl-4 text-left font-medium">
                    <span className="block">{t(`nutrients.${row.key}`, { defaultValue: row.label })}</span>
                    {row.suspect && <span className="text-xs font-semibold text-possible">{t("nutrition.suspect")}</span>}
                  </th>
                  <td className="py-1 pr-1 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      {row.edited && (
                        <span className="rounded-chip bg-beam/15 px-2 py-0.5 text-[0.7rem] font-semibold text-beam">{t("result.edited")}</span>
                      )}
                      {row.amount === null ? (
                        <span className="hatch rounded-md px-2 py-1 text-xs font-semibold text-unknown shadow-[inset_0_0_0_1px_var(--unknown)]">
                          {t("nutrition.cantRead")}
                        </span>
                      ) : (
                        <span className="font-semibold tabular-nums">
                          {formatNumber(row.amount, lang)} {row.unit}
                        </span>
                      )}
                      {locatable && (
                        <IconButton
                          label={t("result.evidence.show", { text: row.rawText || row.label })}
                          onClick={() => focusEvidence(locatable, row.amount === null ? "unknown" : null)}
                        >
                          <LocateFixed className="size-4" aria-hidden="true" />
                        </IconButton>
                      )}
                      {row.fieldPath ? (
                        <IconButton
                          label={t("nutrition.edit", { name: t(`nutrients.${row.key}`, { defaultValue: row.label }) })}
                          onClick={() =>
                            row.fieldPath &&
                            onEdit({
                              kind: "nutrient",
                              fieldPath: row.fieldPath,
                              label: row.label,
                              current: row.amount,
                              unit: row.unit,
                              rawText: row.rawText,
                            })
                          }
                        >
                          <Pencil className="size-4" aria-hidden="true" />
                        </IconButton>
                      ) : (
                        <span className="w-11" aria-hidden="true" />
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {analysis?.notes.map((note) => (
        <p key={note} className="text-sm text-text-dim">
          <Message messageKey={note} params={analysis.servings_per_pack ? { servings: analysis.servings_per_pack } : {}} />
        </p>
      ))}
    </div>
  );
}
