export type ButtonVariant = "primary" | "secondary" | "ghost";
export type ButtonSize = "md" | "lg";

const BASE =
  "relative inline-flex items-center justify-center gap-2 rounded-chip font-semibold whitespace-nowrap select-none " +
  "transition-[transform,opacity,background-color,box-shadow] duration-fast ease-out active:scale-[0.97] " +
  "disabled:pointer-events-none disabled:opacity-50";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-[image:var(--beam-gradient)] text-on-beam shadow-[var(--glow-beam)] hover:opacity-95",
  secondary: "bg-surface text-text shadow-[inset_0_0_0_1px_var(--line)] hover:bg-surface-2",
  ghost: "text-text hover:bg-surface-2",
};

const SIZES: Record<ButtonSize, string> = {
  md: "min-h-11 px-5 text-sm",
  lg: "min-h-[3.25rem] px-6 text-[0.95rem]",
};

export function buttonClasses(variant: ButtonVariant = "primary", size: ButtonSize = "md", extra = ""): string {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]} ${extra}`.trim();
}
