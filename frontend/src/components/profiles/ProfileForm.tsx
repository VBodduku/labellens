import { Check, Quote, X } from "lucide-react";
import { useId } from "react";
import { useTranslation } from "react-i18next";
import { PROFILE_COLORS, restrictionFromCatalog } from "../../lib/profileParse";
import { restrictionLabel } from "../../lib/restrictionLabel";
import type { Profile, Restriction, RestrictionCatalogItem, RestrictionKind, Severity } from "../../shared/contract";
import { useUiStore } from "../../store/ui";
import { IconButton } from "../ui/IconButton";
import { ThresholdControl } from "./ThresholdControl";

const KIND_ORDER: RestrictionKind[] = ["allergy", "intolerance", "diet", "health_limit", "avoid"];
const SEVERITIES: Severity[] = ["strict", "preference"];

interface ProfileFormProps {
  profile: Profile;
  catalog: RestrictionCatalogItem[];
  onChange: (next: Profile) => void;
  nameError?: string | null;
}

/**
 * Edits one family member: name, colour, restrictions picked from the catalog (grouped by kind), severity
 * per restriction and, where needed, the nutrient limit. Restrictions keep any `source_text` they came with.
 */
export function ProfileForm({ profile, catalog, onChange, nameError }: ProfileFormProps) {
  const { t } = useTranslation();
  const lang = useUiStore((state) => state.lang);
  const nameId = useId();
  const selectedKeys = new Set(profile.restrictions.map((restriction) => restriction.key));

  function setRestrictions(restrictions: Restriction[]) {
    onChange({ ...profile, restrictions });
  }

  function toggle(item: RestrictionCatalogItem) {
    if (selectedKeys.has(item.key)) setRestrictions(profile.restrictions.filter((restriction) => restriction.key !== item.key));
    else setRestrictions([...profile.restrictions, restrictionFromCatalog(item)]);
  }

  function update(id: string, patch: Partial<Restriction>) {
    setRestrictions(profile.restrictions.map((restriction) => (restriction.id === id ? { ...restriction, ...patch } : restriction)));
  }

  const groups = KIND_ORDER.map((kind) => ({ kind, items: catalog.filter((item) => item.kind === kind) })).filter((group) => group.items.length > 0);

  return (
    <div className="space-y-5">
      <div>
        <label htmlFor={nameId} className="block text-sm font-semibold">
          {t("profiles.name")}
        </label>
        <input
          id={nameId}
          value={profile.name}
          onChange={(event) => onChange({ ...profile, name: event.target.value })}
          autoComplete="off"
          aria-invalid={Boolean(nameError)}
          className="mt-2 min-h-12 w-full rounded-xl bg-surface-2 px-4 text-base shadow-[inset_0_0_0_1px_var(--line)] focus:shadow-[inset_0_0_0_2px_var(--beam)] focus:outline-none"
        />
        {nameError && (
          <p role="alert" className="mt-1.5 text-sm text-conflict">
            {nameError}
          </p>
        )}
      </div>

      <fieldset>
        <legend className="text-sm font-semibold">{t("profiles.color")}</legend>
        <div role="radiogroup" aria-label={t("profiles.color")} className="mt-2 flex flex-wrap gap-1">
          {PROFILE_COLORS.map((color) => {
            const selected = profile.color?.toLowerCase() === color.toLowerCase();
            return (
              <button
                key={color}
                type="button"
                role="radio"
                aria-checked={selected}
                aria-label={t("profiles.colorOption", { color })}
                onClick={() => onChange({ ...profile, color })}
                className="flex size-11 items-center justify-center rounded-full"
              >
                <span
                  className={`flex size-8 items-center justify-center rounded-full ${selected ? "ring-2 ring-text ring-offset-2 ring-offset-surface" : ""}`}
                  style={{ background: color }}
                >
                  {selected && <Check className="size-4 text-[#0b0d12]" aria-hidden="true" />}
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {profile.restrictions.length > 0 && (
        <ul className="space-y-2">
          {profile.restrictions.map((restriction) => (
            <li key={restriction.id} className="rounded-xl p-3 shadow-[inset_0_0_0_1px_var(--line)]">
              <div className="flex items-start gap-2">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{restrictionLabel(restriction.key, restriction.label, lang)}</p>
                  {restriction.source_text && (
                    <p className="mt-1 flex items-start gap-1.5 text-xs text-text-dim">
                      <Quote className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
                      <span>
                        {t("profiles.fromYourWords")} <q className="italic text-text">{restriction.source_text}</q>
                      </span>
                    </p>
                  )}
                </div>
                <IconButton
                  label={t("profiles.removeRestriction", { name: restrictionLabel(restriction.key, restriction.label, lang) })}
                  onClick={() => setRestrictions(profile.restrictions.filter((candidate) => candidate.id !== restriction.id))}
                  className="-mr-2 -mt-2"
                >
                  <X className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
              <div role="radiogroup" aria-label={t("profiles.severity")} className="mt-2 flex rounded-chip bg-surface-2 p-1">
                {SEVERITIES.map((severity) => (
                  <button
                    key={severity}
                    type="button"
                    role="radio"
                    aria-checked={restriction.severity === severity}
                    onClick={() => update(restriction.id, { severity })}
                    className={`min-h-10 flex-1 rounded-chip px-2 text-xs font-semibold touch:min-h-11 transition-colors duration-fast ${
                      restriction.severity === severity ? "bg-surface text-text shadow-[inset_0_0_0_1px_var(--line)]" : "text-text-dim"
                    }`}
                  >
                    {t(`profiles.severity.${severity}`)}
                  </button>
                ))}
              </div>
              {restriction.threshold && (
                <ThresholdControl threshold={restriction.threshold} onChange={(threshold) => update(restriction.id, { threshold })} />
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-4">
        <p className="text-sm font-semibold">{t("profiles.addRestrictions")}</p>
        {groups.map((group) => (
          <fieldset key={group.kind}>
            <legend className="text-xs font-semibold uppercase tracking-wide text-text-dim">{t(`kinds.${group.kind}`)}</legend>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {group.items.map((item) => {
                const selected = selectedKeys.has(item.key);
                return (
                  <button
                    key={item.key}
                    type="button"
                    aria-pressed={selected}
                    title={item.description_en}
                    onClick={() => toggle(item)}
                    className={`inline-flex min-h-10 items-center gap-1.5 rounded-chip px-3 text-sm touch:min-h-11 transition-colors duration-fast ${
                      selected ? "bg-beam/15 font-semibold text-text shadow-[inset_0_0_0_1.5px_var(--beam)]" : "bg-surface-2 text-text-dim hover:text-text"
                    }`}
                  >
                    {selected && <Check className="size-3.5" aria-hidden="true" />}
                    {restrictionLabel(item.key, item.label_en, lang)}
                  </button>
                );
              })}
            </div>
          </fieldset>
        ))}
      </div>
    </div>
  );
}
