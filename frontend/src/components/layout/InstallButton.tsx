import { Download, Share, SquarePlus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { promptInstall, useInstallState } from "../../lib/installPrompt";
import { IconButton } from "../ui/IconButton";
import { Sheet } from "../ui/Sheet";

/**
 * "Install app": Chrome/Edge use their install prompt; iPhone/iPad get the Share → Add to Home Screen
 * steps. Hidden once installed. `icon` sits in the header (wide screens), `inline` under the hero (phones).
 */
export function InstallButton({ variant }: { variant: "icon" | "inline" }) {
  const { t } = useTranslation();
  const { canPrompt, standalone, ios } = useInstallState();
  const [iosOpen, setIosOpen] = useState(false);
  if (standalone || (!canPrompt && !ios)) return null;

  const onClick = () => (canPrompt ? void promptInstall() : setIosOpen(true));
  return (
    <>
      {variant === "icon" ? (
        <IconButton label={t("install.button")} onClick={onClick}>
          <Download className="size-5" aria-hidden="true" />
        </IconButton>
      ) : (
        <button
          type="button"
          onClick={onClick}
          className="inline-flex min-h-11 items-center gap-2 rounded-chip px-3 text-sm font-semibold text-text-dim hover:text-text"
        >
          <Download className="size-4" aria-hidden="true" />
          {t("install.button")}
        </button>
      )}
      <Sheet open={iosOpen} title={t("install.ios.title")} onClose={() => setIosOpen(false)}>
        <ol className="space-y-4">
          <li className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-beam">
              <Share className="size-5" aria-hidden="true" />
            </span>
            {t("install.ios.step1")}
          </li>
          <li className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-beam">
              <SquarePlus className="size-5" aria-hidden="true" />
            </span>
            {t("install.ios.step2")}
          </li>
          <li className="flex items-center gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-surface-2 text-sm font-bold text-beam">3</span>
            {t("install.ios.step3")}
          </li>
        </ol>
      </Sheet>
    </>
  );
}
