import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { LogoMark, Wordmark } from "../layout/Logo";

export function LandingFooter() {
  const { t } = useTranslation();
  return (
    <footer className="border-t border-line">
      <div className="page-gutter mx-auto flex max-w-page flex-col gap-6 py-10 md:flex-row md:items-start md:justify-between">
        <div className="max-w-md">
          <div className="flex items-center gap-2.5">
            <LogoMark className="size-7" />
            <Wordmark />
          </div>
          <p className="mt-4 text-sm leading-relaxed text-text-dim">{t("landing.footer.disclaimer")}</p>
          <p className="mt-2 text-sm leading-relaxed text-text-dim">{t("landing.footer.privacy")}</p>
        </div>
        <nav aria-label={t("nav.primary")} className="flex gap-1 text-sm font-semibold">
          <Link to="/about" className="inline-flex min-h-11 items-center rounded-chip px-3 text-text-dim hover:text-text">
            {t("nav.about")}
          </Link>
          <Link to="/profiles" className="inline-flex min-h-11 items-center rounded-chip px-3 text-text-dim hover:text-text">
            {t("nav.profiles")}
          </Link>
          <Link to="/scan" className="inline-flex min-h-11 items-center rounded-chip px-3 text-text-dim hover:text-text">
            {t("nav.scan")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
