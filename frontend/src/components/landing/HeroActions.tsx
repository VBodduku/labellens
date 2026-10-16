import { Camera, ScanText } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button, ButtonLink } from "../ui/Button";
import { useDemoLauncher } from "./useDemoLauncher";

/** The two calls to action: a zero-friction demo, and the real camera scan. */
export function HeroActions({ size = "lg", className = "" }: { size?: "md" | "lg"; className?: string }) {
  const { t } = useTranslation();
  const demo = useDemoLauncher();
  return (
    <div className={className}>
      <div className="grid grid-cols-1 gap-2.5 min-[480px]:grid-cols-2 sm:flex sm:flex-wrap sm:gap-3">
        <Button
          size={size}
          onClick={() => void demo.launch()}
          loading={demo.state === "loading"}
          icon={<ScanText className="size-[1.1rem]" aria-hidden="true" />}
        >
          {demo.state === "loading" ? t("landing.cta.demoLoading") : t("landing.cta.demo")}
        </Button>
        <ButtonLink
          to="/scan"
          variant="secondary"
          size={size}
          icon={<Camera className="size-[1.1rem]" aria-hidden="true" />}
        >
          {t("landing.cta.scan")}
        </ButtonLink>
      </div>
      {demo.state === "error" && (
        <p role="alert" className="mt-3 text-sm text-conflict">
          {t("errors.INTERNAL")}
        </p>
      )}
    </div>
  );
}
