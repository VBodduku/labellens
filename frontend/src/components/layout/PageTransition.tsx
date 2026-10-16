import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT = [0.2, 0.8, 0.2, 1] as const;

/** Route enter/exit: a short rise + fade; reduced motion gets a plain crossfade. */
export function PageTransition({ children }: { children: ReactNode }) {
  const reduce = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduce ? 0 : 12 }}
      animate={{ opacity: 1, y: 0, transition: { duration: 0.26, ease: EASE_OUT } }}
      exit={{ opacity: 0, y: reduce ? 0 : -8, transition: { duration: 0.16, ease: EASE_OUT } }}
    >
      {children}
    </motion.div>
  );
}
