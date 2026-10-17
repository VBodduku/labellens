import { ArrowDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { NutrientSide, NutritionComparison } from "../../lib/compare";
import { formatNumber } from "../../lib/format";
import { useUiStore } from "../../store/ui";

function Cell({ side, unit }: { side: NutrientSide; unit: string }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  if (side.status === "not_printed") return <span className="text-xs text-text-dim">{t("compare.nutrition.notPrinted")}</span>;
  if (side.status === "unreadable" || side.amount === null) {
    return (
      <span className="hatch rounded-md px-2 py-1 text-xs font-semibold text-unknown shadow-[inset_0_0_0_1px_var(--unknown)]">
        {t("nutrition.cantRead")}
      </span>
    );
  }
  return (
    <span className="inline-flex flex-col items-end">
      <span className="font-semibold tabular-nums">
        {formatNumber(Math.round(side.amount * 10) / 10, lang)} {unit}
      </span>
      {side.status === "suspect" && <span className="text-[0.7rem] font-semibold text-possible">{t("nutrition.suspect")}</span>}
      {side.status === "ok" && side.derived && <span className="text-[0.7rem] text-text-dim">{t("nutrition.calculated")}</span>}
    </span>
  );
}

/** Per-100 values of both products in one table; a large difference is named in words, never by colour alone. */
export function NutritionCompare({ comparison }: { comparison: NutritionComparison }) {
  const { t } = useTranslation();
  const { comparable, unitA, unitB, rows } = comparison;

  if (rows.length === 0) return <p className="card p-5 text-sm text-text-dim">{t("nutrition.empty")}</p>;

  return (
    <div className="space-y-3">
      {!comparable && (
        <p role="status" className="hatch rounded-xl p-3 text-sm shadow-[inset_0_0_0_1px_var(--unknown)]">
          {t("compare.nutrition.units", { unitA, unitB })}
        </p>
      )}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-text-dim">
              <th scope="col" className="py-2.5 pl-4 font-semibold">
                {t("compare.nutrition.title", { unit: comparable ? unitA : `${unitA} / ${unitB}` })}
              </th>
              <th scope="col" className="py-2.5 pr-3 text-right font-semibold">{t("compare.productA")}</th>
              <th scope="col" className="py-2.5 pr-4 text-right font-semibold">{t("compare.productB")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((row) => (
              <tr key={row.key} className={row.difference ? "bg-surface-2/60" : undefined}>
                <th scope="row" className="py-2.5 pl-4 text-left font-medium">
                  <span className="block">{t(`nutrients.${row.key}`)}</span>
                  {row.difference && (
                    <span className="mt-0.5 inline-flex items-center gap-1 text-xs font-semibold text-text-dim">
                      <ArrowDown className="size-3.5" aria-hidden="true" />
                      {t("compare.nutrition.less", {
                        product: t(row.difference.lower === "a" ? "compare.letterA" : "compare.letterB"),
                        pct: Math.round(row.difference.pct),
                      })}
                    </span>
                  )}
                </th>
                <td className="py-2 pr-3 text-right align-top">
                  <Cell side={row.a} unit={row.unit} />
                </td>
                <td className="py-2 pr-4 text-right align-top">
                  <Cell side={row.b} unit={row.unit} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
