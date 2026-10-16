import { useId } from "react";

/** Lens mark: a label frame with corner brackets and the scan beam across it. */
export function LogoMark({ className = "size-8" }: { className?: string }) {
  const gradientId = useId();
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="var(--beam)" />
          <stop offset="1" stopColor="var(--beam-2)" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9" fill="var(--surface-2)" />
      <path
        d="M8 12V9.5A1.5 1.5 0 0 1 9.5 8H12M20 8h2.5A1.5 1.5 0 0 1 24 9.5V12M24 20v2.5a1.5 1.5 0 0 1-1.5 1.5H20M12 24H9.5A1.5 1.5 0 0 1 8 22.5V20"
        fill="none"
        stroke="var(--text)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <rect x="5" y="15.1" width="22" height="1.8" rx="0.9" fill={`url(#${gradientId})`} />
    </svg>
  );
}

/** `compact` hides the wordmark on the narrowest phones, where the header needs the room (the mark remains). */
export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className={`font-display text-[1.05rem] font-bold tracking-tight sm:text-[1.15rem] ${compact ? "max-[419px]:sr-only" : ""}`}>
      Label<span className="text-beam-gradient">Lens</span>
    </span>
  );
}
