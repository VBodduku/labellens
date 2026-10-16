import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Header } from "./Header";
import { OfflineBanner } from "./OfflineBanner";

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-chip bg-surface px-4 text-sm font-semibold focus:not-sr-only focus:fixed focus:left-4 focus:top-2 focus:inline-flex focus:min-h-11 focus:items-center"
      >
        {t("nav.skip")}
      </a>
      <OfflineBanner />
      <Header />
      <main id="main" className="flex-1">
        {children}
      </main>
    </div>
  );
}
