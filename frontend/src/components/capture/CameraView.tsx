import type { RefObject } from "react";
import { ScanBeam } from "../landing/ScanBeam";

const CORNERS = [
  "left-0 top-0 border-l-[3px] border-t-[3px] rounded-tl-[18px]",
  "right-0 top-0 border-r-[3px] border-t-[3px] rounded-tr-[18px]",
  "bottom-0 left-0 border-b-[3px] border-l-[3px] rounded-bl-[18px]",
  "bottom-0 right-0 border-b-[3px] border-r-[3px] rounded-br-[18px]",
];

/** Full-bleed camera preview with the framing guide (dimmed surround, corner brackets) and the beam inside it. */
interface CameraViewProps {
  videoRef: RefObject<HTMLVideoElement>;
  live: boolean;
  ready: boolean;
  /** The panel tray is showing below, so the guide leaves more room at the bottom. */
  withTray: boolean;
}

export function CameraView({ videoRef, live, ready, withTray }: CameraViewProps) {
  return (
    <div className="absolute inset-0 overflow-hidden bg-black">
      <video ref={videoRef} playsInline muted autoPlay className="size-full object-cover" aria-hidden="true" />
      {live && (
        <div
          className={`pointer-events-none absolute inset-0 flex items-center justify-center pt-16 transition-[padding] duration-base ${
            withTray ? "pb-[22rem]" : "pb-[13.5rem]"
          }`}
        >
          <div className="relative aspect-[3/4] h-full max-h-[34rem] max-w-[82vw] rounded-[18px] shadow-[0_0_0_200vmax_rgb(0_0_0/0.45)]">
            {CORNERS.map((corner) => (
              <span
                key={corner}
                className={`absolute size-9 transition-colors duration-base ${ready ? "border-[var(--beam)]" : "border-white"} ${corner}`}
              />
            ))}
            <div className="absolute inset-3 overflow-hidden rounded-[12px]">
              <ScanBeam overhang={false} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
