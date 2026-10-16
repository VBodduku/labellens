import { ArrowRight, EyeOff, Users } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Reveal, SectionHeading } from "./Reveal";

const ALIASES = [
  ["whey", "milk"],
  ["invert syrup", "sugar"],
  ["INS 120", "animal"],
] as const;

function HiddenNamesVisual() {
  return (
    <ul className="space-y-2" aria-hidden="true">
      {ALIASES.map(([printed, meaning]) => (
        <li key={printed} className="flex items-center gap-2 text-xs">
          <span className="evidence-text rounded-md bg-surface-2 px-2 py-1 text-text">{printed}</span>
          <ArrowRight className="size-3.5 text-text-dim" />
          <span className="font-semibold text-possible">{meaning}</span>
        </li>
      ))}
    </ul>
  );
}

function UnseenVisual() {
  return (
    <div aria-hidden="true" className="space-y-2">
      <p className="evidence-text text-xs text-text">Sugar, Peanuts, Milk Solids,</p>
      <div className="flex items-center gap-2">
        <span className="evidence-text text-xs text-text blur-[2.5px]">Cocoa Butter, Emul</span>
        <span className="hatch inline-flex size-6 items-center justify-center rounded-full text-xs font-bold text-unknown shadow-[inset_0_0_0_1.5px_var(--unknown)]">
          ?
        </span>
      </div>
    </div>
  );
}

function FamilyVisual() {
  return (
    <div aria-hidden="true" className="flex -space-x-2">
      {[
        ["A", "#ff7a59"],
        ["T", "#7c9cff"],
        ["L", "#5fd3a5"],
      ].map(([initial, color]) => (
        <span
          key={initial}
          className="flex size-9 items-center justify-center rounded-full text-sm font-bold text-[#0b0d12] ring-2 ring-surface"
          style={{ background: color }}
        >
          {initial}
        </span>
      ))}
    </div>
  );
}

function PainCard({ icon, title, body, visual, delay }: { icon: ReactNode; title: string; body: string; visual: ReactNode; delay: number }) {
  return (
    <Reveal delay={delay} className="card flex flex-col gap-5 p-6">
      <span className="flex size-10 items-center justify-center rounded-xl bg-surface-2 text-beam">{icon}</span>
      <div>
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-text-dim">{body}</p>
      </div>
      <div className="mt-auto border-t border-line pt-5">{visual}</div>
    </Reveal>
  );
}

export function ProblemSection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="problem-title" className="page-gutter mx-auto max-w-page py-20 lg:py-28">
      <SectionHeading id="problem-title" eyebrow={t("landing.problem.eyebrow")} title={t("landing.problem.title")} />
      <div className="mt-10 grid gap-4 md:grid-cols-3 lg:mt-14 lg:gap-5">
        <PainCard
          delay={0}
          icon={<span className="evidence-text text-sm font-bold">E</span>}
          title={t("landing.problem.hidden.title")}
          body={t("landing.problem.hidden.body")}
          visual={<HiddenNamesVisual />}
        />
        <PainCard
          delay={0.06}
          icon={<EyeOff className="size-5" aria-hidden="true" />}
          title={t("landing.problem.unseen.title")}
          body={t("landing.problem.unseen.body")}
          visual={<UnseenVisual />}
        />
        <PainCard
          delay={0.12}
          icon={<Users className="size-5" aria-hidden="true" />}
          title={t("landing.problem.family.title")}
          body={t("landing.problem.family.body")}
          visual={<FamilyVisual />}
        />
      </div>
    </section>
  );
}
