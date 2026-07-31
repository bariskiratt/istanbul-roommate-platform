import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useI18n } from "@/i18n";

const NotFound = () => {
  const location = useLocation();
  const { t } = useI18n();

  useEffect(() => {
    console.error("404: olmayan rota:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-semibold text-foreground">404</h1>
        <p className="text-lg text-muted-foreground">{t("notfound.text")}</p>
        <Link to="/" className="inline-block text-primary font-semibold underline underline-offset-4 hover:opacity-80">
          {t("notfound.home")}
        </Link>
      </div>
    </div>
  );
};

export default NotFound;
