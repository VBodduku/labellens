import { useTranslation } from "react-i18next";
import { Skeleton } from "../ui/Skeleton";

export function RouteFallback() {
  const { t } = useTranslation();
  return (
    <div className="page-gutter mx-auto max-w-page py-10" role="status" aria-live="polite">
      <span className="sr-only">{t("common.loading")}</span>
      <Skeleton className="h-8 w-2/3 max-w-sm" />
      <Skeleton className="mt-4 h-4 w-full max-w-lg" />
      <Skeleton className="mt-8 h-64 w-full" />
    </div>
  );
}
