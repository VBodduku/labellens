import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey, type ApiError } from "../../api";

interface ErrorNoticeProps {
  error: ApiError;
  title?: string;
  actions?: ReactNode;
}

/** A specific, friendly message per error code (never a raw error), plus retry timing when known. */
export function ErrorNotice({ error, title, actions }: ErrorNoticeProps) {
  const { t } = useTranslation();
  return (
    <div role="alert" className="card flex flex-col gap-4 p-6 sm:p-8">
      <span className="flex size-11 items-center justify-center rounded-full bg-conflict/15 text-conflict">
        <CircleAlert className="size-6" aria-hidden="true" />
      </span>
      <div>
        {title && <h2 className="text-xl font-bold">{title}</h2>}
        <p className="mt-2 leading-relaxed text-text-dim">{t(errorMessageKey(error.code))}</p>
        {error.retryAfterS !== null && (
          <p className="mt-1 text-sm text-text-dim">{t("common.retryIn", { seconds: error.retryAfterS })}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-3">{actions}</div>}
    </div>
  );
}
