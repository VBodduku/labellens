import { motion } from "motion/react";
import type { ReactNode } from "react";

const EASE_OUT = [0.2, 0.8, 0.2, 1] as const;

/** Fades content up once as it enters the viewport (MotionConfig turns this into a fade for reduced motion). */
export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -12% 0px" }}
      transition={{ duration: 0.42, ease: EASE_OUT, delay }}
    >
      {children}
    </motion.div>
  );
}

export function SectionHeading({ eyebrow, title, body, id }: { eyebrow: string; title: string; body?: string; id: string }) {
  return (
    <Reveal className="max-w-2xl">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-beam">{eyebrow}</p>
      <h2 id={id} className="mt-3 text-[clamp(1.7rem,6vw,2.25rem)] font-bold leading-[1.1] sm:text-4xl lg:text-5xl">
        {title}
      </h2>
      {body && <p className="mt-4 text-base leading-relaxed text-text-dim lg:text-lg">{body}</p>}
    </Reveal>
  );
}
