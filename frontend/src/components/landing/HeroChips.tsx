import { m, type MotionValue, useTransform } from "motion/react";
import { useTranslation } from "react-i18next";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { stateColor, stateLabelKey } from "../../lib/verdict";
import type { Box } from "../../shared/contract";
import { StateBadge } from "../verdict/StateBadge";
import { HERO_CHIPS, type HeroChip } from "./heroChipData";
import { useScrollRange } from "./useScrollRange";

/** Scroll progress windows: chip i lifts during [start, start+LIFT], becomes a verdict by start+LIFT+REVEAL. */
const FIRST_START = 0.06;
const STAGGER = 0.15;
const LIFT = 0.07;
const REVEAL = 0.06;

function boxStyle(box: Box) {
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.w * 100}%`,
    height: `${box.h * 100}%`,
  };
}

interface ChipStoryProps {
  chip: HeroChip;
  index: number;
  progress: MotionValue<number>;
  /** Wide screens stack the word above/below its verdict; narrow screens morph the word into the verdict in place. */
  stacked: boolean;
}

function ChipStory({ chip, index, progress, stacked }: ChipStoryProps) {
  const { t } = useTranslation();
  const start = FIRST_START + index * STAGGER;
  const up = chip.direction === "up";
  const liftWindow = [start, start + LIFT] as const;
  const revealWindow = [start + LIFT, start + LIFT + REVEAL] as const;
  const lift = useScrollRange(progress, liftWindow);
  const wordY = useScrollRange(progress, liftWindow, [up ? 14 : -14, 0]);
  const wordScale = useScrollRange(progress, liftWindow, [0.9, 1]);
  const reveal = useScrollRange(progress, revealWindow);
  const beamOutline = useScrollRange(progress, revealWindow, [1, 0]);
  const tagY = useScrollRange(progress, revealWindow, [up ? 10 : -10, 0]);
  const tagScale = useScrollRange(progress, revealWindow, [0.86, 1]);
  const wordOpacity = useTransform([lift, reveal], ([lifted = 0, revealed = 0]: number[]) =>
    stacked ? lifted : lifted * (1 - revealed),
  );
  const anchor = chip.boxes[0];
  if (!anchor) return null;

  const word = (
    <m.span
      style={{ opacity: wordOpacity, y: wordY, scale: wordScale }}
      className="evidence-text inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip bg-surface/95 px-2.5 py-1 text-[0.68rem] font-medium text-text shadow-[inset_0_0_0_1px_var(--beam),var(--glow-beam)] sm:text-xs"
    >
      {chip.word ?? (
        <>
          <span>{chip.nutrient ? t(`nutrients.${chip.nutrient}`) : ""}</span>
          <span className="hatch inline-block h-3 w-8 rounded-sm shadow-[inset_0_0_0_1px_var(--unknown)]" />
        </>
      )}
    </m.span>
  );

  const tag = (
    <m.span
      style={{ opacity: reveal, y: tagY, scale: tagScale }}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip bg-surface py-1 pl-1 pr-2.5 shadow-[inset_0_0_0_1px_var(--line),0_10px_30px_-12px_rgb(0_0_0/0.6)]"
    >
      <StateBadge state={chip.state} unknownKind={chip.unknownKind} size="sm" />
      <span className="size-2 rounded-full" style={{ background: chip.profileColor }} />
      <span className="text-[0.72rem] font-semibold text-text">{chip.profileName}</span>
    </m.span>
  );

  return (
    <>
      {chip.boxes.map((box, boxIndex) => (
        <span key={boxIndex} className="absolute" style={boxStyle(box)}>
          <m.span
            style={{ opacity: beamOutline }}
            className="absolute -inset-[3px] rounded-[4px] shadow-[inset_0_0_0_1.5px_var(--beam),0_0_14px_-2px_var(--beam)]"
          />
          <m.span
            style={{ opacity: reveal, boxShadow: `inset 0 0 0 2px ${stateColor(chip.state)}, 0 0 18px -4px ${stateColor(chip.state)}` }}
            className="absolute -inset-[3px] rounded-[4px]"
          />
        </span>
      ))}
      <span
        className={`absolute -translate-x-1/2 ${up ? "-translate-y-full pb-2" : "pt-2"} ${
          stacked ? "flex flex-col items-center gap-1.5" : "grid place-items-center [&>*]:[grid-area:1/1]"
        }`}
        style={{
          left: `${(anchor.x + anchor.w / 2) * 100}%`,
          top: `${(up ? anchor.y : anchor.y + anchor.h) * 100}%`,
        }}
      >
        {up ? (
          <>
            {tag}
            {word}
          </>
        ) : (
          <>
            {word}
            {tag}
          </>
        )}
      </span>
    </>
  );
}

/** Words lift off the label as glowing chips, then snap into verdict tags as the visitor scrolls. */
export function HeroChips({ progress }: { progress: MotionValue<number> }) {
  const { t } = useTranslation();
  const stacked = useMediaQuery("(min-width: 640px)");
  return (
    <>
      <div aria-hidden="true" className="absolute inset-0">
        {HERO_CHIPS.map((chip, index) => (
          <ChipStory key={chip.id} chip={chip} index={index} progress={progress} stacked={stacked} />
        ))}
      </div>
      <ul className="sr-only" aria-label={t("landing.hero.chipsLabel")}>
        {HERO_CHIPS.map((chip) => (
          <li key={chip.id}>
            {chip.word ?? (chip.nutrient ? t(`nutrients.${chip.nutrient}`) : "")}: {t(stateLabelKey(chip.state, chip.unknownKind))},{" "}
            {chip.profileName}
          </li>
        ))}
      </ul>
    </>
  );
}
