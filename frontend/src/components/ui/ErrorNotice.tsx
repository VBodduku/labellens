import { CircleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { errorMessageKey, type ApiError } from "../../api";
import { useCountdown } from "../../lib/useCountdown";
import { Button } from "./Button";

interface ErrorNoticeProps {
  error: ApiError;
  title?: string;
  /** Shows a Retry button; for RATE_LIMITED it stays disabled until retry_after_s has passed. */
  onRetry?: () => void;
  actions?: ReactNode;
}

/** A specific, friendly message per error code (never a raw error), plus retry timing when known. */
export function ErrorNotice({ error, title, onRetry, actions }: ErrorNoticeProps) {
  const { t } = useTranslation();
  const wait = useCountdown(error.retryAfterS);
  return (
    <div role="alert" className="card flex flex-col gap-4 p-6 sm:p-8">
      <span className="flex size-11 items-center justify-center rounded-full bg-conflict/15 text-conflict">
        <CircleAlert className="size-6" aria-hidden="true" />
      </span>
      <div>
        {title && <h2 className="text-xl font-bold">{title}</h2>}
        <p className="mt-2 leading-relaxed text-text-dim">{t(errorMessageKey(error.code))}</p>
        {wait > 0 && (
          <p className="mt-1 text-sm text-text-dim" aria-live="off">
            {t("common.retryIn", { seconds: wait })}
          </p>
        )}
        {error.requestId && <p className="mt-2 font-mono text-xs text-text-dim">{t("errors.reference", { id: error.requestId })}</p>}
      </div>
      {(onRetry || actions) && (
        <div className="flex flex-wrap gap-3">
          {onRetry && (
            <Button onClick={onRetry} disabled={wait > 0}>
              {wait > 0 ? t("common.retryWait", { seconds: wait }) : t("common.retry")}
            </Button>
          )}
          {actions}
        </div>
      )}
    </div>
  );
}
