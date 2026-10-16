import { useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { CTA } from "../components/landing/CTA";
import { FamilySection } from "../components/landing/FamilySection";
import { Hero } from "../components/landing/Hero";
import { HonestySection } from "../components/landing/HonestySection";
import { HowItWorks } from "../components/landing/HowItWorks";
import { LandingFooter } from "../components/landing/LandingFooter";
import { ProblemSection } from "../components/landing/ProblemSection";
import { useLenis } from "../components/landing/useLenis";

/**
 * The sections below the hero render once the visitor is within a screen of them: the hero's scroll
 * runway keeps them out of view at first, so first paint only pays for the hero.
 */
function useNearViewport() {
  const sentinel = useRef<HTMLDivElement>(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    const node = sentinel.current;
    if (!node || near) return;
    const observer = new IntersectionObserver(([entry]) => entry?.isIntersecting && setNear(true), { rootMargin: "100% 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [near]);
  return { sentinel, near };
}

export default function Landing() {
  const reduce = useReducedMotion() ?? false;
  const { sentinel, near } = useNearViewport();
  useLenis(!reduce);
  return (
    <>
      <Hero />
      <div ref={sentinel} aria-hidden="true" />
      {near ? (
        <>
          <ProblemSection />
          <HowItWorks />
          <HonestySection />
          <FamilySection />
          <CTA />
          <LandingFooter />
        </>
      ) : (
        <div className="min-h-screen" />
      )}
    </>
  );
}
