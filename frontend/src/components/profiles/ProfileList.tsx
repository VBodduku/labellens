import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { restrictionLabel } from "../../lib/restrictionLabel";
import type { Profile } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { Avatar } from "../ui/Avatar";
import { Button } from "../ui/Button";
import { Chip } from "../ui/Chip";
import { IconButton } from "../ui/IconButton";

interface ProfileListProps {
  profiles: Profile[];
  onEdit: (profile: Profile) => void;
  onRemove: (profileId: string) => void;
}

/** Saved family members with their restrictions; removing asks once to confirm. */
export function ProfileList({ profiles, onEdit, onRemove }: ProfileListProps) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const [confirming, setConfirming] = useState<string | null>(null);

  return (
    <ul className="space-y-3">
      {profiles.map((profile) => (
        <li key={profile.profile_id} className="card p-4 sm:p-5">
          <div className="flex items-start gap-3">
            <Avatar name={profile.name} color={profile.color} />
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-bold">{profile.name}</h2>
              {profile.restrictions.length === 0 ? (
                <p className="mt-1 text-sm text-text-dim">{t("profiles.noRestrictions")}</p>
              ) : (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {profile.restrictions.map((restriction) => (
                    <li key={restriction.id}>
                      <Chip>
                        <span className="text-text">{restrictionLabel(restriction.key, restriction.label, lang)}</span>
                        <span>· {t(`profiles.${restriction.severity}`)}</span>
                      </Chip>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <IconButton label={t("profiles.edit", { name: profile.name })} onClick={() => onEdit(profile)}>
              <Pencil className="size-4" aria-hidden="true" />
            </IconButton>
            <IconButton label={t("profiles.remove", { name: profile.name })} onClick={() => setConfirming(profile.profile_id)}>
              <Trash2 className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
          {confirming === profile.profile_id && (
            <div role="alert" className="mt-3 flex flex-wrap items-center gap-2 rounded-xl bg-conflict/10 p-3 text-sm">
              <span className="flex-1">{t("profiles.confirmRemove", { name: profile.name })}</span>
              <Button variant="ghost" onClick={() => setConfirming(null)}>
                {t("common.cancel")}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setConfirming(null);
                  onRemove(profile.profile_id);
                }}
              >
                {t("profiles.removeConfirm")}
              </Button>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}
