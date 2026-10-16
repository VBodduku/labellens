import { useTranslation } from "react-i18next";
import { ButtonLink } from "../components/ui/Button";

export default function NotFound() {
  const { t } = useTranslation();
  return (
    <div className="page-gutter mx-auto flex max-w-xl flex-col items-center py-24 text-center">
      <p className="evidence-text text-sm text-beam">404</p>
      <h1 className="mt-3 text-3xl font-bold">{t("notFound.title")}</h1>
      <p className="mt-3 text-text-dim">{t("notFound.body")}</p>
      <ButtonLink to="/" className="mt-8">
        {t("common.home")}
      </ButtonLink>
    </div>
  );
}
