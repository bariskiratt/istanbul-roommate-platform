import { ArrowLeft } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import Wordmark from "@/components/campus/Wordmark";
import { BRAND } from "@/lib/brand";
import { useI18n } from "@/i18n";

/**
 * Alt menüsü olmayan sayfaların (giriş, kayıt, güvenlik, gizlilik) üst
 * çubuğu: solda logo, sağda dil ve tema. Her sayfa aynı çubuğu kendisi
 * çizerken logo dört yerde dört farklı biçimde kalmıştı.
 */
const SiteBar = ({ showBack = false, right }: { showBack?: boolean; right?: React.ReactNode }) => {
  const navigate = useNavigate();
  const { t } = useI18n();
  return (
    <header className="sticky top-0 z-50 bg-background/90 backdrop-blur-md border-b border-border">
      <div className="max-w-6xl mx-auto px-5 md:px-8 h-16 flex items-center gap-3">
        {showBack && (
          <button
            onClick={() => navigate(-1)}
            aria-label={t("common.back")}
            className="w-10 h-10 -ml-2 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        )}
        <Link to="/" aria-label={BRAND} className="flex-1">
          <Wordmark />
        </Link>
        <div className="flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle />
          {right}
        </div>
      </div>
    </header>
  );
};

export default SiteBar;
