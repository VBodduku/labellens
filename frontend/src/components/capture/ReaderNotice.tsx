import { CloudOff } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../../api";
import { readerStatus, type ReaderStatus } from "../../lib/readerStatus";

/**
 * Says before the photo is taken when the AI reader is unavailable, so a basic reading is no surprise.
 * Asks /api/health once; says nothing while waiting, on success or if the backend can't be reached
 * (the scan itself then reports that error).
 */
export function ReaderNotice() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ReaderStatus | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    api
      .health({ signal: controller.signal })
      .then((health) => setStatus(readerStatus(health)))
      .catch(() => setStatus(null));
    return () => controller.abort();
  }, []);

  if (status !== "local" && status !== "basic") return null;
  return (
    <p
      role="status"
      className="mx-auto flex w-fit max-w-md items-start gap-2 rounded-2xl bg-black/60 px-4 py-2 text-xs font-semibold text-white backdrop-blur-md"
    >
      <CloudOff className="mt-0.5 size-4 shrink-0 text-possible" aria-hidden="true" />
      {t(`scan.reader.${status}`)}
    </p>
  );
}
