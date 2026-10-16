import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { stateColor, stateLabelKey } from "../../lib/verdict";
import type { Box, Evidence, VerdictState } from "../../shared/contract";
import { useUiStore } from "../../store/ui";

export interface OverlayItem {
  evidence: Evidence & { box: Box };
  state: VerdictState | null;
}

interface EvidenceOverlayProps {
  items: OverlayItem[];
  focus: { box: Box; state: VerdictState | null; pulse: number } | null;
}

/**
 * SVG laid exactly over the photo (viewBox 0..1, stretched), drawing every located evidence box:
 * verified = solid, approximate = dashed. Each box is a keyboard/screen-reader hotspot. The focused box
 * gets a mask that dims everything else and an outline that pulses twice in the state colour.
 */
export function EvidenceOverlay({ items, focus }: EvidenceOverlayProps) {
  const { t } = useTranslation();
  const maskId = useId();
  const reduce = useReducedMotion();
  const focusEvidence = useUiStore((store) => store.focusEvidence);

  function onKey(event: KeyboardEvent<SVGRectElement>, item: OverlayItem) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      focusEvidence(item.evidence, item.state);
    }
  }

  return (
    <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 size-full overflow-visible">
      <AnimatePresence>
        {focus && (
          <motion.g key="veil" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduce ? 0 : 0.26 }}>
            <defs>
              <mask id={maskId} maskUnits="userSpaceOnUse" x="0" y="0" width="1" height="1">
                <rect x="0" y="0" width="1" height="1" fill="white" />
                <rect x={focus.box.x} y={focus.box.y} width={focus.box.w} height={focus.box.h} fill="black" />
              </mask>
            </defs>
            <rect x="0" y="0" width="1" height="1" fill="rgb(8 10 14 / 0.58)" mask={`url(#${maskId})`} pointerEvents="none" />
          </motion.g>
        )}
      </AnimatePresence>

      {items.map((item, index) => {
        const { box } = item.evidence;
        const label = item.state
          ? t("result.viewer.hotspot", { text: item.evidence.text, state: t(stateLabelKey(item.state)) })
          : t("result.evidence.show", { text: item.evidence.text });
        return (
          <rect
            key={`${item.evidence.image_id}:${box.x}:${box.y}:${index}`}
            x={box.x}
            y={box.y}
            width={box.w}
            height={box.h}
            rx="0.004"
            fill="transparent"
            stroke={stateColor(item.state)}
            strokeWidth={1.5}
            strokeOpacity={0.9}
            strokeDasharray={item.evidence.status === "approximate" ? "5 4" : undefined}
            vectorEffect="non-scaling-stroke"
            role="button"
            tabIndex={0}
            aria-label={label}
            className="cursor-pointer outline-none focus-visible:[stroke-width:3]"
            onClick={() => focusEvidence(item.evidence, item.state)}
            onKeyDown={(event) => onKey(event, item)}
          />
        );
      })}

      {focus && (
        <motion.rect
          key={focus.pulse}
          x={focus.box.x}
          y={focus.box.y}
          width={focus.box.w}
          height={focus.box.h}
          fill="none"
          stroke={stateColor(focus.state)}
          strokeWidth={3}
          vectorEffect="non-scaling-stroke"
          pointerEvents="none"
          initial={{ opacity: reduce ? 1 : 0 }}
          animate={{ opacity: reduce ? 1 : [0, 1, 0.25, 1, 0.25, 1] }}
          transition={{ duration: 1.3, delay: reduce ? 0 : 0.35, ease: "easeInOut" }}
        />
      )}
    </svg>
  );
}
