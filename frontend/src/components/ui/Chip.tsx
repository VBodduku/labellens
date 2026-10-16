import type { HTMLAttributes } from "react";

export function Chip({ className = "", children, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded-chip bg-surface-2 px-3 text-xs font-medium text-text-dim ${className}`}
      {...rest}
    >
      {children}
    </span>
  );
}
