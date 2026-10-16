import { Flashlight, FlashlightOff } from "lucide-react";
import { useTranslation } from "react-i18next";

export function TorchToggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  const { t } = useTranslation();
  const label = on ? t("scan.torch.off") : t("scan.torch.on");
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={label}
      aria-pressed={on}
      title={label}
      className={`flex size-11 items-center justify-center rounded-full backdrop-blur-md transition-colors duration-fast ${
        on ? "bg-white text-black" : "bg-black/50 text-white"
      }`}
    >
      {on ? <FlashlightOff className="size-5" aria-hidden="true" /> : <Flashlight className="size-5" aria-hidden="true" />}
    </button>
  );
}
