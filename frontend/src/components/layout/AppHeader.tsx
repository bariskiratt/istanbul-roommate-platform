import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import Wordmark from "@/components/campus/Wordmark";
import { BRAND } from "@/lib/brand";
import { useI18n } from "@/i18n";

interface AppHeaderProps {
  title: string;
  showBack?: boolean;
  /** Geri düğmesi geçmişe değil belirli bir sayfaya dönsün (ör. Ayarlar → Profil). */
  onBack?: () => void;
  rightAction?: React.ReactNode;
  /** Tema/dil düğmelerini gizler (dar başlıklar için). */
  hideControls?: boolean;
}

const AppHeader = ({ title, showBack = false, onBack, rightAction, hideControls = false }: AppHeaderProps) => {
  const navigate = useNavigate();
  const { t } = useI18n();

  return (
    <header className="nav-header sticky top-0 z-50 px-5 h-16 flex items-center gap-3">
      {showBack && (
        <button
          onClick={onBack ?? (() => navigate(-1))}
          aria-label={t("common.back")}
          className="-ml-2 w-10 h-10 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
      )}
      {/* Başlık markanın kendisiyse başlık yerine logo göster. Karşılaştırma
          BRAND üzerinden: iki yerde elle yazılsaydı biri değişince logo
          sessizce kaybolurdu. */}
      {!showBack && title === BRAND ? (
        <button onClick={() => navigate("/")} className="flex-1 text-left" aria-label={BRAND}>
          <Wordmark />
        </button>
      ) : (
        <h1 className="font-display text-[1.6rem] font-semibold flex-1 text-foreground truncate leading-none">{title}</h1>
      )}
      {!hideControls && (
        <div className="flex items-center gap-1">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      )}
      {rightAction}
    </header>
  );
};

export default AppHeader;
