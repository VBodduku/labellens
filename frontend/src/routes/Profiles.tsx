import { Trash2, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { IconButton } from "../components/ui/IconButton";
import { Skeleton } from "../components/ui/Skeleton";
import { useProfilesStore } from "../store/profiles";

export default function Profiles() {
  const { t } = useTranslation();
  const { profiles, hydrated, remove, replaceAll } = useProfilesStore();
  const [addingDemo, setAddingDemo] = useState(false);

  async function addDemoFamily() {
    setAddingDemo(true);
    try {
      const { fixtureProfiles } = await import("../api/fixtures");
      await replaceAll(structuredClone(fixtureProfiles));
    } finally {
      setAddingDemo(false);
    }
  }

  return (
    <div className="page-gutter mx-auto max-w-2xl py-8 lg:py-12">
      <h1 className="text-3xl font-bold">{t("profiles.title")}</h1>
      <p className="mt-2 text-text-dim">{t("profiles.subtitle")}</p>

      {!hydrated ? (
        <div className="mt-6 space-y-3" role="status" aria-live="polite">
          <span className="sr-only">{t("profiles.loading")}</span>
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : profiles.length === 0 ? (
        <div className="card mt-6 flex flex-col items-center gap-4 p-8 text-center">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-surface-2 text-beam">
            <Users className="size-6" aria-hidden="true" />
          </span>
          <h2 className="text-xl font-bold">{t("profiles.empty.title")}</h2>
          <p className="max-w-sm text-sm text-text-dim">{t("profiles.empty.body")}</p>
          <Button variant="secondary" loading={addingDemo} onClick={() => void addDemoFamily()}>
            {t("profiles.useDemo")}
          </Button>
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {profiles.map((profile) => (
            <li key={profile.profile_id} className="card flex items-start gap-4 p-4 sm:p-5">
              <span
                aria-hidden="true"
                className="flex size-11 shrink-0 items-center justify-center rounded-full font-bold text-[#0b0d12]"
                style={{ background: profile.color ?? "var(--beam)" }}
              >
                {profile.name.slice(0, 1)}
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="text-base font-bold">{profile.name}</h2>
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {profile.restrictions.map((restriction) => (
                    <li key={restriction.id}>
                      <Chip>
                        {restriction.label}
                        <span className="text-text-dim/80">· {t(`profiles.${restriction.severity}`)}</span>
                      </Chip>
                    </li>
                  ))}
                </ul>
              </div>
              <IconButton label={t("profiles.remove", { name: profile.name })} onClick={() => void remove(profile.profile_id)}>
                <Trash2 className="size-5" aria-hidden="true" />
              </IconButton>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
