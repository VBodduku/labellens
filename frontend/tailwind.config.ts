import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

const token = (name: string) => `var(--${name})`;

/** Colour backed by a CSS variable that still supports Tailwind opacity modifiers (bg-conflict/15). */
const colorToken = (name: string) => `color-mix(in srgb, var(--${name}) calc(<alpha-value> * 100%), transparent)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: colorToken("bg"),
        surface: colorToken("surface"),
        "surface-2": colorToken("surface-2"),
        line: colorToken("line"),
        text: colorToken("text"),
        "text-dim": colorToken("text-dim"),
        beam: colorToken("beam"),
        "beam-2": colorToken("beam-2"),
        "on-beam": colorToken("on-beam"),
        conflict: colorToken("conflict"),
        possible: colorToken("possible"),
        "not-listed": colorToken("not-listed"),
        unknown: colorToken("unknown"),
        "on-verdict": colorToken("on-verdict"),
      },
      fontFamily: {
        display: token("font-display"),
        body: token("font-body"),
        mono: token("font-mono"),
      },
      borderRadius: {
        card: token("radius-card"),
        chip: token("radius-chip"),
      },
      transitionTimingFunction: {
        out: token("ease-out"),
      },
      transitionDuration: {
        fast: token("dur-fast"),
        base: token("dur-base"),
        slow: token("dur-slow"),
      },
      maxWidth: {
        page: "76rem",
      },
    },
  },
  plugins: [
    // `touch:` = coarse pointer (phones/tablets): grow controls to 44 px targets without bloating desktop.
    plugin(({ addVariant }) => addVariant("touch", "@media (pointer: coarse)")),
  ],
} satisfies Config;
