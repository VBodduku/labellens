import { useTranslation } from "react-i18next";
import type { FamilyRow } from "../../lib/compare";
import { restrictionLabel } from "../../lib/restrictionLabel";
import type { RestrictionResult } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { Avatar } from "../ui/Avatar";
import { Message } from "../ui/Message";
import { StateBadge } from "../verdict/StateBadge";

function Verdict({ result }: { result: RestrictionResult | null }) {
  const { t } = useTranslation();
  if (!result) return <span className="text-xs text-text-dim">{t("compare.family.noResult")}</span>;
  const quote = result.evidence.find((evidence) => evidence.text)?.text;
  return (
    <div className="space-y-1">
      <StateBadge state={result.state} unknownKind={result.unknown_kind} size="sm" />
      <p className="text-xs text-text-dim">
        <Message messageKey={result.message_key} params={result.message_params} />
      </p>
      {quote && (
        <p lang="" className="evidence-text text-xs text-text">
          “{quote}”
        </p>
      )}
    </div>
  );
}

/** Each family member's engine verdict for product A and product B, with the reasons one tap away. */
export function FamilyCompare({ rows }: { rows: FamilyRow[] }) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const letterA = t("compare.letterA");
  const letterB = t("compare.letterB");

  if (rows.length === 0) return <p className="card p-5 text-sm text-text-dim">{t("compare.family.noProfiles")}</p>;

  return (
    <ul className="space-y-3">
      {rows.map(({ profile, a, b, restrictions }) => (
        <li key={profile.profile_id} className="card p-4">
          <div className="flex items-center gap-3">
            <Avatar name={profile.name} color={profile.color} size="sm" />
            <h3 className="min-w-0 flex-1 truncate font-bold">{profile.name}</h3>
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-3">
            {([["a", a], ["b", b]] as const).map(([side, report]) => (
              <div key={side} className="rounded-xl bg-surface-2 p-3">
                <dt className="text-xs font-semibold text-text-dim">{t(side === "a" ? "compare.productA" : "compare.productB")}</dt>
                <dd className="mt-1.5">
                  {report ? (
                    <StateBadge state={report.overall} size="md" />
                  ) : (
                    <span className="text-xs text-text-dim">{t("compare.family.noResult")}</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
          {restrictions.length > 0 && (
            <details className="group mt-3">
              <summary className="min-h-10 cursor-pointer touch:min-h-11 text-sm font-semibold text-beam">{t("compare.family.why")}</summary>
              <ul className="mt-2 divide-y divide-line">
                {restrictions.map(({ restriction, a: resultA, b: resultB }) => (
                  <li key={restriction.id} className="py-3">
                    <p className="text-sm font-semibold">{restrictionLabel(restriction.key, restriction.label, lang)}</p>
                    <div className="mt-2 grid grid-cols-2 gap-3">
                      <div>
                        <p className="mb-1 text-[0.7rem] font-bold text-text-dim">{letterA}</p>
                        <Verdict result={resultA} />
                      </div>
                      <div>
                        <p className="mb-1 text-[0.7rem] font-bold text-text-dim">{letterB}</p>
                        <Verdict result={resultB} />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}
