import { UserPlus, Users } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { useTranslation } from "react-i18next";
import { ProfileList } from "../components/profiles/ProfileList";
import { SentenceInput } from "../components/profiles/SentenceInput";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { createId } from "../lib/ids";
import { useLatch } from "../lib/useLatch";
import { finalizeParsedProfiles, nextColor } from "../lib/profileParse";
import type { Profile, ProfileParseResponse } from "../shared/contract";
import { useProfilesStore } from "../store/profiles";

const ProfileEditor = lazy(() => import("../components/profiles/ProfileEditor").then((module) => ({ default: module.ProfileEditor })));
const ParseConfirmSheet = lazy(() =>
  import("../components/profiles/ParseConfirmSheet").then((module) => ({ default: module.ParseConfirmSheet })),
);

/** Family members (§5.5): add by form or by describing them in a sentence; stored only on this device. */
export default function Profiles() {
  const { t } = useTranslation();
  const { profiles, hydrated, add, update, remove, replaceAll } = useProfilesStore();
  const [editing, setEditing] = useState<{ profile: Profile; isNew: boolean } | null>(null);
  const [parsed, setParsed] = useState<ProfileParseResponse | null>(null);
  const [addingDemo, setAddingDemo] = useState(false);
  const editorMounted = useLatch(editing !== null);
  const confirmMounted = useLatch(parsed !== null);

  function startNew() {
    setEditing({
      profile: { profile_id: createId("p"), name: "", color: nextColor(profiles.map((profile) => profile.color)), restrictions: [] },
      isNew: true,
    });
  }

  async function saveProfile(profile: Profile) {
    const isNew = editing?.isNew ?? false;
    setEditing(null);
    await (isNew ? add(profile) : update(profile));
  }

  async function confirmParsed(proposed: Profile[]) {
    setParsed(null);
    const fresh = finalizeParsedProfiles(proposed, profiles);
    await replaceAll([...profiles, ...fresh]);
  }

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
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{t("profiles.title")}</h1>
          <p className="mt-2 text-text-dim">{t("profiles.subtitle")}</p>
        </div>
        {profiles.length > 0 && (
          <Button onClick={startNew} icon={<UserPlus className="size-4" aria-hidden="true" />}>
            {t("profiles.add")}
          </Button>
        )}
      </div>

      <div className="mt-6 space-y-6">
        {!hydrated ? (
          <div className="space-y-3" role="status" aria-live="polite">
            <span className="sr-only">{t("profiles.loading")}</span>
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </div>
        ) : profiles.length === 0 ? (
          <>
            <div className="card flex flex-col items-center gap-3 p-6 text-center">
              <span className="flex size-12 items-center justify-center rounded-2xl bg-surface-2 text-beam">
                <Users className="size-6" aria-hidden="true" />
              </span>
              <h2 className="text-xl font-bold">{t("profiles.empty.title")}</h2>
              <p className="max-w-sm text-sm text-text-dim">{t("profiles.empty.body")}</p>
            </div>
            <SentenceInput onParsed={setParsed} />
            <div className="flex flex-wrap justify-center gap-3">
              <Button variant="secondary" onClick={startNew} icon={<UserPlus className="size-4" aria-hidden="true" />}>
                {t("profiles.addByForm")}
              </Button>
              <Button variant="ghost" loading={addingDemo} onClick={() => void addDemoFamily()}>
                {t("profiles.useDemo")}
              </Button>
            </div>
          </>
        ) : (
          <>
            <ProfileList profiles={profiles} onEdit={(profile) => setEditing({ profile, isNew: false })} onRemove={(id) => void remove(id)} />
            <SentenceInput onParsed={setParsed} />
          </>
        )}
      </div>

      <Suspense fallback={null}>
        {editorMounted && (
          <ProfileEditor
            profile={editing?.profile ?? null}
            isNew={editing?.isNew ?? false}
            onClose={() => setEditing(null)}
            onSave={(profile) => void saveProfile(profile)}
          />
        )}
        {confirmMounted && (
          <ParseConfirmSheet response={parsed} onCancel={() => setParsed(null)} onConfirm={(proposed) => void confirmParsed(proposed)} />
        )}
      </Suspense>
    </div>
  );
}
