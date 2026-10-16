import { motion, useTransform, type MotionValue } from "motion/react";
import { useTranslation } from "react-i18next";
import { stateLabelKey } from "../../lib/verdict";
import type { Box } from "../../shared/contract";
import { StateBadge } from "../verdict/StateBadge";
import { HERO_CHIPS, type HeroChip } from "./heroChipData";

/** Scroll progress windows: chip i lifts during [start, start+LIFT], becomes a verdict by start+LIFT+REVEAL. */
const FIRST_START = 0.06;
const STAGGER = 0.15;
const LIFT = 0.07;
const REVEAL = 0.06;

const STATE_COLOR: Record<HeroChip["state"], string> = {
  conflict: "var(--conflict)",
  possible: "var(--possible)",
  not_listed: "var(--not-listed)",
  unknown: "var(--unknown)",
};

function boxStyle(box: Box) {
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.w * 100}%`,
    height: `${box.h * 100}%`,
  };
}

function ChipStory({ chip, index, progress }: { chip: HeroChip; index: number; progress: MotionValue<number> }) {
  const { t } = useTranslation();
  const start = FIRST_START + index * STAGGER;
  const lift = useTransform(progress, [start, start + LIFT], [0, 1]);
  const reveal = useTransform(progress, [start + LIFT, start + LIFT + REVEAL], [0, 1]);
  const beamOutline = useTransform(reveal, (value) => 1 - value);
  const up = chip.direction === "up";
  const wordY = useTransform(lift, [0, 1], [up ? 14 : -14, 0]);
  const wordScale = useTransform(lift, [0, 1], [0.9, 1]);
  const tagY = useTransform(reveal, [0, 1], [up ? 10 : -10, 0]);
  const tagScale = useTransform(reveal, [0, 1], [0.86, 1]);
  const anchor = chip.boxes[0];
  if (!anchor) return null;

  const word = (
    <motion.span
      style={{ opacity: lift, y: wordY, scale: wordScale }}
      className="evidence-text inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip bg-surface/95 px-2.5 py-1 text-[0.68rem] font-medium text-text shadow-[inset_0_0_0_1px_var(--beam),var(--glow-beam)] sm:text-xs"
    >
      {chip.word ?? (
        <>
          <span>{chip.nutrient ? t(`nutrients.${chip.nutrient}`) : ""}</span>
          <span className="hatch inline-block h-3 w-8 rounded-sm shadow-[inset_0_0_0_1px_var(--unknown)]" />
        </>
      )}
    </motion.span>
  );

  const tag = (
    <motion.span
      style={{ opacity: reveal, y: tagY, scale: tagScale }}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-chip bg-surface py-1 pl-1 pr-2.5 shadow-[inset_0_0_0_1px_var(--line),0_10px_30px_-12px_rgb(0_0_0/0.6)]"
    >
      <StateBadge state={chip.state} unknownKind={chip.unknownKind} size="sm" />
      <span className="size-2 rounded-full" style={{ background: chip.profileColor }} />
      <span className="text-[0.72rem] font-semibold text-text">{chip.profileName}</span>
    </motion.span>
  );

  return (
    <>
      {chip.boxes.map((box, boxIndex) => (
        <span key={boxIndex} className="absolute" style={boxStyle(box)}>
          <motion.span
            style={{ opacity: beamOutline }}
            className="absolute -inset-[3px] rounded-[4px] shadow-[inset_0_0_0_1.5px_var(--beam),0_0_14px_-2px_var(--beam)]"
          />
          <motion.span
            style={{ opacity: reveal, boxShadow: `inset 0 0 0 2px ${STATE_COLOR[chip.state]}, 0 0 18px -4px ${STATE_COLOR[chip.state]}` }}
            className="absolute -inset-[3px] rounded-[4px]"
          />
        </span>
      ))}
      <span
        className={`absolute flex -translate-x-1/2 flex-col items-center gap-1.5 ${up ? "-translate-y-full pb-2" : "pt-2"}`}
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
  return (
    <>
      <div aria-hidden="true" className="absolute inset-0">
        {HERO_CHIPS.map((chip, index) => (
          <ChipStory key={chip.id} chip={chip} index={index} progress={progress} />
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

export const HERO_STORY_END = FIRST_START + (HERO_CHIPS.length - 1) * STAGGER + LIFT + REVEAL;
