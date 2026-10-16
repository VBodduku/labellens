import { useReducedMotion } from "motion/react";
import { CTA } from "../components/landing/CTA";
import { FamilySection } from "../components/landing/FamilySection";
import { Hero } from "../components/landing/Hero";
import { HonestySection } from "../components/landing/HonestySection";
import { HowItWorks } from "../components/landing/HowItWorks";
import { LandingFooter } from "../components/landing/LandingFooter";
import { ProblemSection } from "../components/landing/ProblemSection";
import { useLenis } from "../components/landing/useLenis";

export default function Landing() {
  const reduce = useReducedMotion() ?? false;
  useLenis(!reduce);
  return (
    <>
      <Hero />
      <ProblemSection />
      <HowItWorks />
      <HonestySection />
      <FamilySection />
      <CTA />
      <LandingFooter />
    </>
  );
}
