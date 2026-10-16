import { AnimatePresence, motion } from "motion/react";
import { useTranslation } from "react-i18next";
import type { RestrictionResult } from "../../shared/contract";
import { EvidenceChips } from "../evidence/EvidenceChip";
import { RetakeLink } from "../label/RetakeLink";
import { Message } from "../ui/Message";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { StateBadge } from "./StateBadge";
import { WhyDisclosure } from "./WhyDisclosure";

const resultItemVariants = {
  hidden: { opacity: 0, y: 14 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.26, ease: [0.2, 0.8, 0.2, 1] } },
} as const;

interface ResultCardProps {
  result: RestrictionResult;
  label: string;
  /** The verdict's state changed in the last recheck: morph the badge and flash the card. */
  changed: boolean;
}

/** One restriction: state badge, label, the engine's message, the evidence behind it, why, and confidence. */
export function ResultCard({ result, label, changed }: ResultCardProps) {
  const { t } = useTranslation();
  const stateKey = `${result.state}:${result.unknown_kind ?? ""}`;
  const unreadableRegion = result.state === "unknown" ? result.evidence.find((item) => item.box && item.status !== "unverified") : undefined;
  return (
    <motion.li variants={resultItemVariants} className="relative p-4 sm:p-5">
      <AnimatePresence>
        {changed && (
          <motion.span
            key={stateKey}
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 shadow-[inset_0_0_0_2px_var(--beam)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0, 1, 0] }}
            transition={{ duration: 1.6 }}
          />
        )}
      </AnimatePresence>
      <div className="flex flex-wrap items-center gap-2">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={stateKey}
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.7 }}
            transition={{ type: "spring", stiffness: 520, damping: 30 }}
            className="inline-flex"
          >
            <StateBadge state={result.state} unknownKind={result.unknown_kind} size="sm" />
          </motion.span>
        </AnimatePresence>
        <h4 className="text-sm font-semibold">{label}</h4>
        {changed && <span className="text-xs font-semibold text-beam">{t("result.changed")}</span>}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-text-dim">
        <Message messageKey={result.message_key} params={result.message_params} />
      </p>
      <EvidenceChips evidence={result.evidence} state={result.state} className="mt-3" />
      {unreadableRegion && <RetakeLink imageId={unreadableRegion.image_id} className="mt-3" />}
      <div className="flex flex-wrap items-end justify-between gap-x-4">
        <WhyDisclosure matches={result.matches} />
        <ConfidenceMeter value={result.confidence} />
      </div>
    </motion.li>
  );
}
