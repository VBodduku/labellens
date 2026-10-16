import type { ButtonHTMLAttributes, ReactNode } from "react";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible name — icon buttons have no visible text. */
  label: string;
  children: ReactNode;
}

export function IconButton({ label, className = "", children, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={
        "inline-flex size-11 shrink-0 items-center justify-center rounded-chip text-text-dim transition-[transform,background-color,color] " +
        `duration-fast ease-out hover:bg-surface-2 hover:text-text active:scale-95 ${className}`
      }
      {...rest}
    >
      {children}
    </button>
  );
}
