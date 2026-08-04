import { ArrowLeft, Home } from "lucide-react";
import { useNavigate } from "react-router-dom";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import { BRAND } from "@/lib/brand";

interface AppHeaderProps {
  title: string;
  showBack?: boolean;
  rightAction?: React.ReactNode;
  /** Tema/dil düğmelerini gizler (dar başlıklar için). */
  hideControls?: boolean;
}

const AppHeader = ({ title, showBack = false, rightAction, hideControls = false }: AppHeaderProps) => {
  const navigate = useNavigate();

  return (
    <header className="nav-header sticky top-0 z-50 px-6 py-4 flex items-center gap-3">
      {showBack && (
        <button
          onClick={() => navigate(-1)}
          className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
      )}
      {/* Başlık markanın kendisiyse başlık yerine logo göster. Karşılaştırma
          BRAND üzerinden: iki yerde elle yazılsaydı biri değişince logo
          sessizce kaybolurdu. */}
      {!showBack && title === BRAND ? (
        <div className="flex items-center gap-2 flex-1 cursor-pointer" onClick={() => navigate("/")}>
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
            <Home className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-extrabold text-lg text-foreground tracking-tight">{BRAND}</span>
        </div>
      ) : (
        <h1 className="font-bold text-xl flex-1 text-foreground">{title}</h1>
      )}
      {!hideControls && (
        <div className="flex items-center gap-1.5">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      )}
      {rightAction}
    </header>
  );
};

export default AppHeader;
