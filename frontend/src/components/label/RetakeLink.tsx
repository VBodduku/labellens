import { Camera } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { imageIndex } from "../../lib/boxMath";
import { ButtonLink } from "../ui/Button";

/** Opens the camera to replace the panel an unreadable region is on; the scan reruns after the new photo. */
export function RetakeLink({ imageId, className = "" }: { imageId: string; className?: string }) {
  const { t } = useTranslation();
  const { search } = useLocation();
  const params = new URLSearchParams(search);
  params.set("retake", String(imageIndex(imageId)));
  return (
    <ButtonLink
      to={{ pathname: "/scan", search: `?${params.toString()}` }}
      variant="secondary"
      className={className}
      icon={<Camera className="size-4" aria-hidden="true" />}
    >
      {t("unknowns.retake")}
    </ButtonLink>
  );
}
