import { WifiOff } from "lucide-react";
import { useSyncExternalStore } from "react";
import { useTranslation } from "react-i18next";

function subscribe(listener: () => void) {
  window.addEventListener("online", listener);
  window.addEventListener("offline", listener);
  return () => {
    window.removeEventListener("online", listener);
    window.removeEventListener("offline", listener);
  };
}

/** Tells people up front when there is no connection (the demo label keeps working offline). */
export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true);
  if (online) return null;
  return (
    <p role="status" className="flex items-center justify-center gap-2 bg-possible px-4 py-2 text-center text-sm font-semibold text-on-verdict">
      <WifiOff className="size-4 shrink-0" aria-hidden="true" />
      {t("offline.banner")}
    </p>
  );
}
