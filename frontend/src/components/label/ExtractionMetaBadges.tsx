import { Cpu, FileText, ScanSearch } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { ExtractionMeta } from "../../shared/contract";

function MetaBadge({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="inline-flex min-h-7 items-center gap-1.5 rounded-chip bg-surface-2 px-2.5 text-xs font-semibold text-text-dim">
      {icon}
      {children}
    </li>
  );
}

/** How the label was read: re-read passes, on-device fallback, or text-only mode. Cache hits stay hidden. */
export function ExtractionMetaBadges({ meta }: { meta: ExtractionMeta }) {
  const { t } = useTranslation();
  const badges: ReactNode[] = [];
  if (meta.retries.length > 0) {
    badges.push(
      <MetaBadge key="retries" icon={<ScanSearch className="size-3.5" aria-hidden="true" />}>
        {t("meta.doubleChecked", { count: meta.retries.length })}
      </MetaBadge>,
    );
  }
  if (meta.provider === "ollama") {
    badges.push(
      <MetaBadge key="ollama" icon={<Cpu className="size-3.5" aria-hidden="true" />}>
        {t("meta.onDevice")}
      </MetaBadge>,
    );
  }
  if (meta.provider === "ocr_only") {
    badges.push(
      <MetaBadge key="ocr" icon={<FileText className="size-3.5" aria-hidden="true" />}>
        {t("meta.limited")}
      </MetaBadge>,
    );
  }
  if (badges.length === 0) return null;
  return <ul className="flex flex-wrap gap-2">{badges}</ul>;
}
