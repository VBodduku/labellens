import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import type { Profile } from "../../shared/contract";
import { Button } from "../ui/Button";
import { ErrorNotice } from "../ui/ErrorNotice";
import { Sheet } from "../ui/Sheet";
import { Skeleton } from "../ui/Skeleton";
import { ProfileForm } from "./ProfileForm";
import { useCatalog } from "./useCatalog";

interface ProfileEditorProps {
  /** Profile being edited (a fresh draft for "Add"); null closes the editor. */
  profile: Profile | null;
  isNew: boolean;
  onClose: () => void;
  onSave: (profile: Profile) => void;
}

/** Add or edit one family member, with restrictions from the engine's catalog. */
export function ProfileEditor({ profile, isNew, onClose, onSave }: ProfileEditorProps) {
  const { t } = useTranslation();
  const catalog = useCatalog();
  const [draft, setDraft] = useState<Profile | null>(profile);
  const [nameError, setNameError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(profile);
    setNameError(null);
  }, [profile]);

  function save() {
    if (!draft) return;
    if (!draft.name.trim()) {
      setNameError(t("profiles.nameRequired"));
      return;
    }
    onSave({ ...draft, name: draft.name.trim() });
  }

  return (
    <Sheet open={profile !== null} title={isNew ? t("profiles.addTitle") : t("profiles.editTitle")} onClose={onClose} wide>
      {draft && (
        <>
          {catalog.status === "loading" && (
            <div className="space-y-3" role="status">
              <span className="sr-only">{t("common.loading")}</span>
              <Skeleton className="h-12" />
              <Skeleton className="h-40" />
            </div>
          )}
          {catalog.status === "error" && (
            <ErrorNotice error={catalog.error} actions={<Button onClick={() => void catalog.retry()}>{t("common.retry")}</Button>} />
          )}
          {catalog.status === "ready" && <ProfileForm profile={draft} catalog={catalog.items} onChange={setDraft} nameError={nameError} />}
          <div className="sticky -bottom-5 -mx-5 mt-6 flex justify-end gap-2 border-t border-line bg-surface px-5 pb-1 pt-3">
            <Button variant="ghost" onClick={onClose}>
              {t("common.cancel")}
            </Button>
            <Button onClick={save} disabled={catalog.status !== "ready"}>
              {t("profiles.save")}
            </Button>
          </div>
        </>
      )}
    </Sheet>
  );
}
