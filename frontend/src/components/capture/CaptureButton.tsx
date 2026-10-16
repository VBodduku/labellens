import { motion, type MotionValue } from "motion/react";
import { useTranslation } from "react-i18next";

interface CaptureButtonProps {
  progress: MotionValue<number>;
  disabled: boolean;
  onCapture: () => void;
}

/** Manual shutter; the ring around it fills while every quality check is passing (auto-capture at full). */
export function CaptureButton({ progress, disabled, onCapture }: CaptureButtonProps) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onCapture}
      disabled={disabled}
      aria-label={t("scan.shutter")}
      className="relative flex size-[4.75rem] shrink-0 items-center justify-center rounded-full transition-transform duration-fast ease-out active:scale-95 disabled:opacity-40"
    >
      <svg viewBox="0 0 80 80" className="absolute inset-0 size-full -rotate-90" aria-hidden="true">
        <circle cx="40" cy="40" r="36" fill="none" stroke="rgb(255 255 255 / 0.35)" strokeWidth="4" />
        <motion.circle
          cx="40"
          cy="40"
          r="36"
          fill="none"
          stroke="var(--beam)"
          strokeWidth="4"
          strokeLinecap="round"
          style={{ pathLength: progress }}
        />
      </svg>
      <span className="size-[3.6rem] rounded-full bg-white shadow-[0_0_0_2px_rgb(0_0_0/0.15)_inset]" />
    </button>
  );
}
