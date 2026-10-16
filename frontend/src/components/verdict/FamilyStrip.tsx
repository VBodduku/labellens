import { m } from "motion/react";
import { useTranslation } from "react-i18next";
import { sortWorstFirst } from "../../lib/verdict";
import type { Profile, ProfileReport } from "../../shared/contract";
import { StateBadge } from "./StateBadge";

interface FamilyStripProps {
  reports: ProfileReport[];
  profiles: Profile[];
  selectedId: string | null;
  onSelect: (profileId: string) => void;
}

/** One chip per family member with their overall state; the selection underline glides between them. */
export function FamilyStrip({ reports, profiles, selectedId, onSelect }: FamilyStripProps) {
  const { t } = useTranslation();
  return (
    <div role="group" aria-label={t("result.family.label")} className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
      {reports.map((report) => {
        const profile = profiles.find((candidate) => candidate.profile_id === report.profile_id);
        const name = profile?.name ?? report.profile_id;
        const worst = sortWorstFirst(report.results)[0];
        const selected = report.profile_id === selectedId;
        return (
          <button
            key={report.profile_id}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(report.profile_id)}
            className={`relative flex min-h-14 shrink-0 items-center gap-2.5 rounded-card py-2 pl-2 pr-3 text-left transition-colors duration-fast ${
              selected ? "bg-surface shadow-[inset_0_0_0_1px_var(--line)]" : "hover:bg-surface"
            }`}
          >
            <span
              aria-hidden="true"
              className="flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-[#0b0d12]"
              style={{ background: profile?.color ?? "var(--beam)" }}
            >
              {name.slice(0, 1)}
            </span>
            <span className="flex flex-col items-start gap-1">
              <span className="text-sm font-bold leading-none">{name}</span>
              <StateBadge state={report.overall} unknownKind={worst?.state === "unknown" ? worst.unknown_kind : null} size="sm" />
            </span>
            {selected && (
              <m.span
                layoutId="family-selection"
                className="absolute inset-x-3 -bottom-px h-[3px] rounded-full bg-[var(--beam-gradient)]"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
