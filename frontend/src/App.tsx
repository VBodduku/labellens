import { AnimatePresence, LazyMotion, MotionConfig } from "motion/react";
import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { PageTransition } from "./components/layout/PageTransition";
import { RouteFallback } from "./components/layout/RouteFallback";
import { useProfilesStore } from "./store/profiles";
import { useScanStore } from "./store/scan";

// Every route is its own chunk; Three.js and Lenis are reachable only from Landing.
const Landing = lazy(() => import("./routes/Landing"));
const Scan = lazy(() => import("./routes/Scan"));
const Result = lazy(() => import("./routes/Result"));
const Profiles = lazy(() => import("./routes/Profiles"));
const About = lazy(() => import("./routes/About"));
const NotFound = lazy(() => import("./routes/NotFound"));

/** Animation features arrive as their own chunk; `m` components render statically until then. */
const loadMotionFeatures = () => import("./lib/motionFeatures").then((module) => module.default);

export function App() {
  const location = useLocation();
  const hydrateProfiles = useProfilesStore((state) => state.hydrate);
  const hydrateScan = useScanStore((state) => state.hydrate);

  useEffect(() => {
    void hydrateProfiles();
    void hydrateScan();
  }, [hydrateProfiles, hydrateScan]);

  return (
    <LazyMotion features={loadMotionFeatures} strict>
      <MotionConfig reducedMotion="user">
        <AppShell>
          <AnimatePresence mode="wait" initial={false} onExitComplete={() => window.scrollTo({ top: 0 })}>
            <PageTransition key={location.pathname}>
              <Suspense fallback={<RouteFallback />}>
                <Routes location={location}>
                  <Route path="/" element={<Landing />} />
                  <Route path="/scan" element={<Scan />} />
                  <Route path="/result" element={<Result />} />
                  <Route path="/profiles" element={<Profiles />} />
                  <Route path="/about" element={<About />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </PageTransition>
          </AnimatePresence>
        </AppShell>
      </MotionConfig>
    </LazyMotion>
  );
}
