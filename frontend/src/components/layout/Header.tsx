import { Info, Users } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";
import { InstallButton } from "./InstallButton";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { LogoMark, Wordmark } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { to: "/profiles", labelKey: "nav.profiles", Icon: Users, mobile: true },
  { to: "/about", labelKey: "nav.about", Icon: Info, mobile: false },
] as const;

export function Header() {
  const { t } = useTranslation();
  return (
    <header className="sticky top-0 z-40 border-b border-line/60 bg-bg/75 backdrop-blur-xl supports-[backdrop-filter]:bg-bg/60">
      <div className="page-gutter mx-auto flex h-16 max-w-page items-center gap-1 sm:gap-2">
        <Link to="/" aria-label={t("nav.home")} className="mr-auto flex min-h-11 min-w-11 items-center gap-2.5 rounded-chip pr-2">
          <LogoMark />
          <Wordmark compact />
        </Link>
        <nav aria-label={t("nav.primary")} className="flex items-center">
          {NAV.map(({ to, labelKey, Icon, mobile }) => (
            <NavLink
              key={to}
              to={to}
              aria-label={t(labelKey)}
              className={({ isActive }) =>
                `${mobile ? "inline-flex" : "hidden sm:inline-flex"} min-h-11 min-w-11 items-center justify-center gap-2 rounded-chip px-2 text-sm font-semibold transition-colors duration-fast md:px-3.5 ${
                  isActive ? "text-text" : "text-text-dim hover:text-text"
                }`
              }
            >
              <Icon className="size-5 md:hidden" aria-hidden="true" />
              <span className="hidden md:inline">{t(labelKey)}</span>
            </NavLink>
          ))}
        </nav>
        <LanguageSwitcher />
        <div className="hidden sm:block">
          <InstallButton variant="icon" />
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
