import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Header } from "./Header";

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-chip bg-surface px-4 py-2 text-sm font-semibold focus:not-sr-only focus:fixed focus:left-4 focus:top-3"
      >
        {t("nav.skip")}
      </a>
      <Header />
      <main id="main" className="flex-1">
        {children}
      </main>
    </div>
  );
}
