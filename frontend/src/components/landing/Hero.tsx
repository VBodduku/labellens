import { ChevronDown } from "lucide-react";
import { m, useMotionValue, useReducedMotion, useScroll } from "motion/react";
import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { InstallButton } from "../layout/InstallButton";
import { HeroActions } from "./HeroActions";
import { HeroStage } from "./HeroStage";
import { useScrollRange } from "./useScrollRange";

/**
 * A sticky hero on a tall scroll runway: scrolling drives the chip story on the label.
 * Reduced motion: no runway, the finished verdict tags are shown immediately.
 */
export function Hero() {
  const { t } = useTranslation();
  const runway = useRef<HTMLElement>(null);
  const reduce = useReducedMotion() ?? false;
  const { scrollYProgress } = useScroll({ target: runway, offset: ["start start", "end end"] });
  const finished = useMotionValue(1);
  const progress = reduce ? finished : scrollYProgress;
  const hintOpacity = useScrollRange(scrollYProgress, [0, 0.05], [1, 0]);

  return (
    <section ref={runway} aria-labelledby="hero-title" className={reduce ? "relative overflow-x-clip" : "relative h-[220vh] overflow-x-clip lg:h-[260vh]"}>
      <div className="sticky top-16 h-[calc(100svh-4rem)] min-h-[34rem]">
        <div className="page-gutter mx-auto grid h-full max-w-page grid-rows-[minmax(0,1fr)_auto] gap-5 pb-6 pt-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:grid-rows-1 lg:items-center lg:gap-12 lg:py-10">
          <div className="order-2 lg:order-1">
            <p className="mb-3 inline-flex items-center gap-2 rounded-chip bg-surface-2 py-1.5 pl-2.5 pr-3.5 text-xs font-semibold text-text-dim lg:mb-6">
              <span className="relative flex size-2">
                <span className="absolute inset-0 animate-ping rounded-full bg-beam opacity-60 motion-reduce:animate-none" />
                <span className="relative size-2 rounded-full bg-beam" />
              </span>
              {t("landing.hero.eyebrow")}
            </p>
            <h1
              id="hero-title"
              className="text-[clamp(1.85rem,7.4vw,2.5rem)] font-extrabold leading-[1.04] sm:text-5xl lg:text-[3.2rem] xl:text-[3.6rem]"
            >
              <span className="block">{t("landing.hero.title.lead")}</span>
              <span className="text-beam-gradient block pb-1">{t("landing.hero.title.accent")}</span>
            </h1>
            <p className="mt-3 max-w-xl text-[0.95rem] leading-relaxed text-text-dim [@media(max-height:760px)_and_(max-width:1023px)]:hidden lg:mt-6 lg:text-lg">
              {t("landing.hero.subtitle")}
            </p>
            <HeroActions className="mt-5 lg:mt-9" />
            <div className="mt-1 sm:hidden">
              <InstallButton variant="inline" />
            </div>
            {!reduce && (
              <m.p
                style={{ opacity: hintOpacity }}
                className="mt-8 hidden items-center gap-2 text-sm font-medium text-text-dim lg:flex"
              >
                <ChevronDown className="size-4 animate-bounce" aria-hidden="true" />
                {t("landing.hero.scrollHint")}
              </m.p>
            )}
          </div>
          <div className="relative order-1 min-h-0 lg:order-2 lg:h-full">
            <HeroStage progress={progress} motionAllowed={!reduce} />
          </div>
        </div>
      </div>
    </section>
  );
}
