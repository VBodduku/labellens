import { CircleAlert, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Profile, ProfileParseResponse } from "../../shared/contract";
import { Avatar } from "../ui/Avatar";
import { Button } from "../ui/Button";
import { IconButton } from "../ui/IconButton";
import { Sheet } from "../ui/Sheet";
import { ProfileForm } from "./ProfileForm";
import { useCatalog } from "./useCatalog";

interface ParseConfirmSheetProps {
  response: ProfileParseResponse | null;
  onCancel: () => void;
  onConfirm: (profiles: Profile[]) => void;
}

/**
 * What we understood from the sentence, for the user to check: every proposed person and restriction is
 * editable, each restriction shows the words it came from, and nothing is saved until Confirm.
 */
export function ParseConfirmSheet({ response, onCancel, onConfirm }: ParseConfirmSheetProps) {
  const { t } = useTranslation();
  const catalog = useCatalog();
  const [drafts, setDrafts] = useState<Profile[]>([]);

  useEffect(() => {
    setDrafts(response ? structuredClone(response.profiles) : []);
  }, [response]);

  const named = drafts.filter((draft) => draft.name.trim());

  return (
    <Sheet open={response !== null} title={t("profiles.parse.title")} onClose={onCancel} wide>
      {response && (
        <div className="space-y-5">
          <p className="text-sm text-text-dim">{t("profiles.parse.intro")}</p>

          {response.warnings.length > 0 && (
            <ul className="space-y-2">
              {response.warnings.map((warning) => (
                <li key={warning} className="flex gap-2 rounded-xl bg-possible/10 p-3 text-sm shadow-[inset_0_0_0_1px_var(--possible)]">
                  <CircleAlert className="mt-0.5 size-4 shrink-0 text-possible" aria-hidden="true" />
                  {warning}
                </li>
              ))}
            </ul>
          )}

          {response.unparsed.length > 0 && (
            <div className="rounded-xl p-3 shadow-[inset_0_0_0_1px_var(--unknown)]">
              <p className="text-sm font-semibold">{t("profiles.parse.unparsed")}</p>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {response.unparsed.map((phrase) => (
                  <li key={phrase} className="hatch rounded-md px-2 py-1 text-sm text-unknown">
                    <q>{phrase}</q>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {drafts.length === 0 && <p className="text-sm text-text-dim">{t("profiles.parse.none")}</p>}

          {drafts.map((draft, index) => (
            <section key={draft.profile_id} className="rounded-card p-4 shadow-[inset_0_0_0_1px_var(--line)]">
              <div className="mb-4 flex items-center gap-3">
                <Avatar name={draft.name} color={draft.color} size="sm" />
                <h3 className="flex-1 font-bold">{draft.name.trim() || t("profiles.parse.unnamed", { n: index + 1 })}</h3>
                <IconButton
                  label={t("profiles.remove", { name: draft.name || t("profiles.parse.unnamed", { n: index + 1 }) })}
                  onClick={() => setDrafts(drafts.filter((candidate) => candidate.profile_id !== draft.profile_id))}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
              <ProfileForm
                profile={draft}
                catalog={catalog.items}
                onChange={(next) => setDrafts(drafts.map((candidate) => (candidate.profile_id === draft.profile_id ? next : candidate)))}
              />
            </section>
          ))}

          <div className="sticky -bottom-5 -mx-5 flex justify-end gap-2 border-t border-line bg-surface px-5 pb-1 pt-3">
            <Button variant="ghost" onClick={onCancel}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => onConfirm(named)} disabled={named.length === 0}>
              {t("profiles.parse.confirm", { count: named.length })}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  );
}
