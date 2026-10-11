import { Link, useLocation } from "react-router-dom";
import { useEffect } from "react";
import SiteBar from "@/components/layout/SiteBar";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n";

const NotFound = () => {
  const location = useLocation();
  const { t } = useI18n();

  useEffect(() => {
    console.error("404: olmayan rota:", location.pathname);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <SiteBar />
      <main className="flex-1 w-full max-w-xl mx-auto px-5 py-16 md:py-24">
        {/* Kırmızı kalemle işaretlenmiş yanlış adres */}
        <div className="relative inline-block">
          <h1 className="font-display text-[7rem] md:text-[9rem] leading-none font-semibold text-foreground">404</h1>
          <span className="stamp stamp-red absolute -right-20 md:-right-24 bottom-1 rotate-[-12deg] text-lg px-3 py-1 bg-background/70" aria-hidden="true">
            {t("notfound.stamp")}
          </span>
        </div>
        <p className="mt-6 text-lg text-muted-foreground">{t("notfound.text")}</p>
        <p className="mt-2 text-[13px] text-muted-foreground break-all">{location.pathname}</p>
        <Button asChild size="lg" className="mt-8 h-12 text-base">
          <Link to="/">{t("notfound.home")}</Link>
        </Button>
      </main>
    </div>
  );
};

export default NotFound;
