import { ArrowDown, ListChecks } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Difference, Side } from "../../lib/compare";
import { joinWithAnd, localeFor } from "../../lib/format";
import { useUiStore } from "../../store/ui";

const OTHER_KEY = {
  absent: "compare.diff.absent",
  not_in_readable_part: "compare.diff.notInReadable",
  list_unreadable: "compare.diff.listUnreadable",
} as const;

/** The differences worth pointing out, as plain sentences: what each label lists and how far per-100 values differ. */
export function DifferencesList({ items, per100Unit }: { items: Difference[]; per100Unit: "g" | "ml" }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const letter = (side: Side) => t(side === "a" ? "compare.letterA" : "compare.letterB");
  const other = (side: Side): Side => (side === "a" ? "b" : "a");

  if (items.length === 0) return <p className="card p-5 text-sm text-text-dim">{t("compare.diff.none")}</p>;

  return (
    <ul className="card divide-y divide-line">
      {items.map((item) => {
        const text =
          item.kind === "nutrient"
            ? t("compare.diff.nutrient", {
                product: letter(item.lower),
                other: letter(other(item.lower)),
                pct: Math.round(item.pct),
                nutrient: t(`nutrients.${item.key}`).toLocaleLowerCase(localeFor(lang)),
                unit: per100Unit,
              })
            : t(OTHER_KEY[item.other], {
                product: letter(item.product),
                other: letter(other(item.product)),
                terms: joinWithAnd(item.terms, lang),
                category: t(`categories.${item.category}`),
              });
        const Icon = item.kind === "nutrient" ? ArrowDown : ListChecks;
        return (
          <li key={item.kind === "nutrient" ? `n:${item.key}` : `c:${item.product}:${item.category}`} className="flex gap-3 p-4 text-sm">
            <Icon className="mt-0.5 size-4 shrink-0 text-text-dim" aria-hidden="true" />
            <span>{text}</span>
          </li>
        );
      })}
    </ul>
  );
}
