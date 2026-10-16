/** A family member's initial on their colour. Decorative: the name is always shown next to it. */
export function Avatar({ name, color, size = "md" }: { name: string; color?: string | null; size?: "sm" | "md" | "lg" }) {
  const sizes = { sm: "size-9 text-sm", md: "size-11 text-base", lg: "size-14 text-xl" } as const;
  return (
    <span
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-full font-bold text-[#0b0d12] ${sizes[size]}`}
      style={{ background: color ?? "var(--beam)" }}
    >
      {name.trim().slice(0, 1).toUpperCase() || "?"}
    </span>
  );
}
