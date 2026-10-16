import { useTranslation } from "react-i18next";
import { HeroActions } from "./HeroActions";
import { Reveal } from "./Reveal";
import { ScanBeam } from "./ScanBeam";

export function CTA() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="cta-title" className="page-gutter mx-auto max-w-page py-20 lg:py-28">
      <Reveal className="relative overflow-hidden rounded-[22px] bg-surface p-7 shadow-[inset_0_0_0_1px_var(--line)] sm:p-12 lg:p-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-[radial-gradient(closest-side,color-mix(in_srgb,var(--beam-2)_30%,transparent),transparent)]"
        />
        <ScanBeam overhang={false} className="opacity-60" />
        <div className="relative max-w-2xl">
          <h2 id="cta-title" className="text-[clamp(1.8rem,6.5vw,2.5rem)] font-bold leading-[1.08] lg:text-5xl">
            {t("landing.cta.title")}
          </h2>
          <p className="mt-4 text-base leading-relaxed text-text-dim lg:text-lg">{t("landing.cta.body")}</p>
          <HeroActions className="mt-8" />
        </div>
      </Reveal>
    </section>
  );
}
