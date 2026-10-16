import { CameraOff, Lock, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Spinner } from "../ui/Spinner";
import type { CameraStatus } from "./useCamera";

const ICONS: Partial<Record<CameraStatus, typeof CameraOff>> = {
  denied: Lock,
  unavailable: CameraOff,
  insecure: ShieldAlert,
  error: CameraOff,
};

/** Explains why there is no live camera (or that it is starting) and offers the way forward. */
export function CameraStateCard({ status, actions }: { status: Exclude<CameraStatus, "live">; actions: ReactNode }) {
  const { t } = useTranslation();
  if (status === "requesting") {
    return (
      <div role="status" className="flex items-center gap-3 rounded-chip bg-black/60 px-5 py-3 text-sm font-semibold text-white backdrop-blur-md">
        <Spinner />
        {t("scan.camera.requesting")}
      </div>
    );
  }
  const Icon = ICONS[status] ?? CameraOff;
  const title = status === "error" ? null : t(`scan.camera.${status}.title`);
  const body = status === "error" ? t("scan.camera.error") : t(`scan.camera.${status}.body`);
  return (
    <div role="alert" className="mx-4 max-w-sm rounded-[18px] bg-[#12151c]/90 p-6 text-center text-white backdrop-blur-md">
      <span className="mx-auto flex size-12 items-center justify-center rounded-full bg-white/10">
        <Icon className="size-6" aria-hidden="true" />
      </span>
      {title && <h2 className="mt-4 text-lg font-bold">{title}</h2>}
      <p className="mt-2 text-sm leading-relaxed text-white/75">{body}</p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">{actions}</div>
    </div>
  );
}
