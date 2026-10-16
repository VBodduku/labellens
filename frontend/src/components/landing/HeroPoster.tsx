import { useTranslation } from "react-i18next";
import { sampleLabelUrl } from "../../api/fixtures";
import { ScanBeam } from "./ScanBeam";

/**
 * Static stand-in for the 3D packet: shown while the WebGL chunk loads (fast LCP), and permanently
 * when WebGL is unavailable or the visitor prefers reduced motion. The label image fills its parent
 * exactly, so evidence boxes line up with the words.
 */
export function HeroPoster({ beam = true }: { beam?: boolean }) {
  const { t } = useTranslation();
  return (
    <>
      <div className="absolute -inset-2 rounded-[14px] bg-[linear-gradient(145deg,#4a2419,#2a130e)] shadow-[inset_0_1px_0_rgb(255_255_255/0.14),0_40px_70px_-35px_rgb(0_0_0/0.85)] sm:-inset-3 sm:rounded-[18px]" />
      <div className="absolute inset-0 overflow-hidden rounded-[6px]">
        <img
          src={sampleLabelUrl}
          alt={t("landing.hero.posterAlt")}
          width={1000}
          height={1400}
          fetchPriority="high"
          decoding="async"
          draggable={false}
          className="size-full select-none object-fill"
        />
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,rgb(255_255_255/0.2),transparent_38%,transparent_70%,rgb(255_255_255/0.08))]" />
      </div>
      {beam && <ScanBeam />}
    </>
  );
}
