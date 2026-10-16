import { useTranslation } from "react-i18next";
import { ScanBeam } from "./ScanBeam";

/** Pre-rendered from the fixture SVG by scripts/render-poster.mjs (cheap to paint, unlike the live SVG). */
export const HERO_POSTER_URL = "/hero-poster.webp";
const HERO_POSTER_SRCSET = "/hero-poster-500.webp 500w, /hero-poster.webp 1000w";
/** The poster is at most ~40 % of the viewport wide on large screens and ~60 % on phones. */
const HERO_POSTER_SIZES = "(min-width: 1024px) 34vw, 62vw";

/** React 18 only forwards the lowercase attribute; it marks the poster as the LCP image. */
const FETCH_PRIORITY_HIGH = { fetchpriority: "high" } as Record<string, string>;

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
          src={HERO_POSTER_URL}
          srcSet={HERO_POSTER_SRCSET}
          sizes={HERO_POSTER_SIZES}
          alt={t("landing.hero.posterAlt")}
          width={1000}
          height={1400}
          {...FETCH_PRIORITY_HIGH}
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
