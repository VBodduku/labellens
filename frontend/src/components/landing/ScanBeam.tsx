/**
 * The signature motif: a thin line of light with a soft glow sweeping down its container.
 * Pure CSS transform animation; frozen part-way down under prefers-reduced-motion.
 */
export function ScanBeam({ className = "", overhang = true }: { className?: string; overhang?: boolean }) {
  return (
    <div aria-hidden="true" className={`pointer-events-none absolute inset-0 overflow-visible ${className}`}>
      <div className="scan-beam-track absolute inset-x-0 -top-full h-full">
        <div className={`absolute bottom-0 ${overhang ? "-left-[12%] -right-[12%]" : "inset-x-0"}`}>
          <div className="absolute inset-x-[8%] bottom-0 h-16 bg-[linear-gradient(to_top,color-mix(in_srgb,var(--beam)_28%,transparent),transparent)]" />
          <div className="relative h-[2px] rounded-full bg-[linear-gradient(90deg,transparent,var(--beam)_18%,var(--beam-2)_82%,transparent)] shadow-[0_0_12px_2px_color-mix(in_srgb,var(--beam)_70%,transparent)]" />
        </div>
      </div>
    </div>
  );
}
