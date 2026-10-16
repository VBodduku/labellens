import { useEffect, useState } from "react";

/** Whole seconds left from `seconds` (counts down once per second; null = no countdown). */
export function useCountdown(seconds: number | null): number {
  const [left, setLeft] = useState(() => Math.max(0, Math.ceil(seconds ?? 0)));

  useEffect(() => {
    setLeft(Math.max(0, Math.ceil(seconds ?? 0)));
    if (!seconds || seconds <= 0) return;
    const endsAt = Date.now() + seconds * 1000;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, Math.ceil((endsAt - Date.now()) / 1000));
      setLeft(remaining);
      if (remaining === 0) window.clearInterval(timer);
    }, 250);
    return () => window.clearInterval(timer);
  }, [seconds]);

  return left;
}
