import { Camera, ListChecks, ScanSearch, ScanText, Sparkles } from "lucide-react";
import { motion, useReducedMotion, useScroll, type MotionValue } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { SectionHeading } from "./Reveal";
import { useScrollRange } from "./useScrollRange";

const STEPS = [
  { id: "capture", Icon: Camera },
  { id: "read", Icon: ScanText },
  { id: "understand", Icon: Sparkles },
  { id: "verify", Icon: ScanSearch },
  { id: "decide", Icon: ListChecks },
] as const;

function Step({ index, progress, children }: { index: number; progress: MotionValue<number>; children: React.ReactNode }) {
  const at = index / (STEPS.length - 1);
  const lit = useScrollRange(progress, [Math.max(0, at - 0.12) - 0.001, at], [0.35, 1]);
  const reduce = useReducedMotion();
  return (
    <motion.li style={{ opacity: reduce ? 1 : lit }} className="relative flex gap-4 lg:flex-col lg:gap-5">
      {children}
    </motion.li>
  );
}

/** Five-step pipeline; a beam travels along the connector as the section scrolls into view. */
export function HowItWorks() {
  const { t } = useTranslation();
  const list = useRef<HTMLOListElement>(null);
  const { scrollYProgress } = useScroll({ target: list, offset: ["start 0.85", "end 0.55"] });
  const reduce = useReducedMotion();
  const scrolled = useScrollRange(scrollYProgress, [0, 1]);
  const line = reduce ? 1 : scrolled;

  return (
    <section aria-labelledby="how-title" className="relative overflow-hidden border-y border-line bg-surface py-20 lg:py-28">
      <div className="page-gutter mx-auto max-w-page">
        <SectionHeading id="how-title" eyebrow={t("landing.how.eyebrow")} title={t("landing.how.title")} />
        <div className="relative mt-12 lg:mt-16">
          <div aria-hidden="true" className="absolute bottom-6 left-[1.375rem] top-6 w-px bg-line lg:hidden">
            <motion.div
              style={{ scaleY: line }}
              className="absolute inset-0 origin-top bg-[linear-gradient(to_bottom,var(--beam),var(--beam-2))] shadow-[0_0_10px_var(--beam)]"
            />
          </div>
          <div aria-hidden="true" className="absolute left-6 right-6 top-[1.375rem] hidden h-px bg-line lg:block">
            <motion.div
              style={{ scaleX: line }}
              className="absolute inset-0 origin-left bg-[var(--beam-gradient)] shadow-[0_0_10px_var(--beam)]"
            />
          </div>
          <ol ref={list} className="relative grid gap-8 lg:grid-cols-5 lg:gap-6">
            {STEPS.map(({ id, Icon }, index) => (
              <Step key={id} index={index} progress={scrollYProgress}>
                <span className="relative z-10 flex size-11 shrink-0 items-center justify-center rounded-full bg-surface-2 text-beam shadow-[inset_0_0_0_1px_var(--line)]">
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <div>
                  <p className="evidence-text text-xs text-text-dim">0{index + 1}</p>
                  <h3 className="mt-1 text-lg font-bold">{t(`landing.how.${id}.title`)}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-text-dim">{t(`landing.how.${id}.body`)}</p>
                </div>
              </Step>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
