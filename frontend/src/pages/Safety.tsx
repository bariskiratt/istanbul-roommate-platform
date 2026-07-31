import { useNavigate } from "react-router-dom";
import { Shield, ShieldCheck, MessageCircle, KeyRound, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";

const Safety = () => {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const { t } = useI18n();

  // NOT: Bu sayfa yalnızca üründe gerçekten var olan güvenceleri anlatır.
  // "Yapay zeka moderasyonu" ve "uçtan uca şifreli mesajlaşma" iddiaları
  // kaldırıldı — ikisi de uygulanmış değil.
  const cards = [
    { icon: ShieldCheck, title: t("safety.card1Title"), desc: t("safety.card1Desc") },
    { icon: MessageCircle, title: t("safety.card2Title"), desc: t("safety.card2Desc") },
    { icon: KeyRound, title: t("safety.card3Title"), desc: t("safety.card3Desc") },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-card/95 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <button onClick={() => navigate("/")} className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-lg text-foreground tracking-tight">RoomMatch</span>
          </button>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
            <Button
              onClick={() => navigate(isLoggedIn ? "/swipe" : "/onboarding")}
              className="bg-primary text-primary-foreground rounded-full text-sm font-bold px-5"
            >
              {t(isLoggedIn ? "safety.backToApp" : "landing.getStarted")}
            </Button>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-16 space-y-16">
        <div className="text-center space-y-4">
          <div className="w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center mx-auto">
            <Shield className="w-10 h-10 text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground">{t("safety.title")}</h1>
          <p className="text-muted-foreground max-w-xl mx-auto">{t("safety.sub")}</p>
        </div>

        <div className="grid md:grid-cols-3 gap-10">
          {cards.map((section, i) => (
            <div key={i} className="text-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
                <section.icon className="w-7 h-7 text-primary" />
              </div>
              <h3 className="text-lg font-bold text-foreground">{section.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{section.desc}</p>
            </div>
          ))}
        </div>

        <div className="card-listing p-6 max-w-2xl mx-auto text-center space-y-2">
          <h2 className="text-lg font-bold text-foreground">{t("safety.tipsTitle")}</h2>
          <p className="text-sm text-muted-foreground leading-relaxed">{t("safety.tips")}</p>
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-background border-t border-border">
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-4">
          <button onClick={() => navigate("/")} className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-3.5 h-3.5 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-foreground">RoomMatch</span>
          </button>
          <p className="text-xs text-muted-foreground">© 2026 RoomMatch. {t("safety.rights")}</p>
        </div>
      </footer>
    </div>
  );
};

export default Safety;
