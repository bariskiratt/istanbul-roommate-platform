import { useNavigate } from "react-router-dom";
import { Shield, ShieldCheck, ScanSearch, MessageCircle, Lock, Flag, KeyRound, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import ThemeToggle from "@/components/ThemeToggle";
import LanguageToggle from "@/components/LanguageToggle";
import { BRAND } from "@/lib/brand";

const Safety = () => {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const { t } = useI18n();

  // NOT: Bu sayfa yalnızca üründe gerçekten uygulanmış güvenceleri anlatır.
  // Metindeki hassas noktalar bilerek sınırlandırıldı — değiştirirken bozma:
  //  - card2 (denetim): kural katmanı her zaman açık, yapay zeka katmanı yalnızca
  //    ANTHROPIC_API_KEY tanımlıysa çalışır. O katman açıkken metnin TAMAMI
  //    Anthropic'e gidiyor (moderation_ai.py); bu, kullanıcıya açıkça söylenir.
  //    Ayrıca denetim şifrelemeden ÖNCE düz metin üzerinde çalışır — card4 ile
  //    yan yana okununca çelişki doğmasın diye bu da yazılıdır.
  //  - card4 (şifreleme): koşulludur. crypto.py MESSAGE_KEY yoksa sessizce DÜZ
  //    METİN yazar, bu yüzden cümle "anahtar yapılandırıldığında" diye kurulur.
  //    Anahtar sunucuda olduğu için bu UÇTAN UCA şifreleme DEĞİLDİR.
  //  - card6 (silme): ilan silme aslında yayından kaldırmadır (is_active=False),
  //    satır veritabanında kalır; yalnızca HESAP silme kalıcıdır (auth.delete_account).
  const cards = [
    { icon: ShieldCheck, title: t("safety.card1Title"), desc: t("safety.card1Desc") },
    { icon: ScanSearch, title: t("safety.card2Title"), desc: t("safety.card2Desc") },
    { icon: MessageCircle, title: t("safety.card3Title"), desc: t("safety.card3Desc") },
    { icon: Lock, title: t("safety.card4Title"), desc: t("safety.card4Desc") },
    { icon: Flag, title: t("safety.card5Title"), desc: t("safety.card5Desc") },
    { icon: KeyRound, title: t("safety.card6Title"), desc: t("safety.card6Desc") },
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
            <span className="font-extrabold text-lg text-foreground tracking-tight">{BRAND}</span>
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

        <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-x-8 gap-y-12">
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
            <span className="font-extrabold text-foreground">{BRAND}</span>
          </button>
          <p className="text-xs text-muted-foreground">© 2026 {BRAND}. {t("safety.rights")}</p>
        </div>
      </footer>
    </div>
  );
};

export default Safety;
