import { Monitor, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useUiStore, type ThemeChoice } from "../../store/ui";
import { IconButton } from "../ui/IconButton";

const ICONS: Record<ThemeChoice, typeof Sun> = { system: Monitor, light: Sun, dark: Moon };

export function ThemeToggle() {
  const { t } = useTranslation();
  const theme = useUiStore((state) => state.theme);
  const cycleTheme = useUiStore((state) => state.cycleTheme);
  const Icon = ICONS[theme];
  return (
    <IconButton label={t("theme.toggle", { mode: t(`theme.${theme}`) })} onClick={cycleTheme}>
      <Icon className="size-5" aria-hidden="true" />
    </IconButton>
  );
}
