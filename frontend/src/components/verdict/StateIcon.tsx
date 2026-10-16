import type { VerdictState } from "../../shared/contract";

/** Distinct shapes per state (octagon-X, triangle-!, circle-check, dashed circle-?) so colour is never the only cue. */
export function StateIcon({ state, className = "size-4" }: { state: VerdictState; className?: string }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2.2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className,
    "aria-hidden": true,
  };
  switch (state) {
    case "conflict":
      return (
        <svg {...common}>
          <path d="M8.2 2.5h7.6l5.7 5.7v7.6l-5.7 5.7H8.2l-5.7-5.7V8.2z" />
          <path d="m9 9 6 6M15 9l-6 6" />
        </svg>
      );
    case "possible":
      return (
        <svg {...common}>
          <path d="M10.3 3.6 2.4 17.4A2 2 0 0 0 4.1 20.4h15.8a2 2 0 0 0 1.7-3L13.7 3.6a2 2 0 0 0-3.4 0z" />
          <path d="M12 9v4.2M12 16.8h.01" />
        </svg>
      );
    case "not_listed":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9.5" />
          <path d="m8 12.3 2.7 2.7L16.2 9.5" />
        </svg>
      );
    case "unknown":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9.5" strokeDasharray="3.2 2.6" />
          <path d="M9.6 9.4a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.1-2.4 3.5M12 16.8h.01" />
        </svg>
      );
  }
}
