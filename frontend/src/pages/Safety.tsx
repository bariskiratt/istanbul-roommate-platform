import { useNavigate } from "react-router-dom";
import { ShieldCheck, ScanSearch, MessageCircle, Lock, Flag, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import SiteBar from "@/components/layout/SiteBar";
import Wordmark from "@/components/campus/Wordmark";
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
      <SiteBar
        right={
          <Button onClick={() => navigate(isLoggedIn ? "/swipe" : "/onboarding")} className="ml-1 px-5">
            {t(isLoggedIn ? "safety.backToApp" : "landing.getStarted")}
          </Button>
        }
      />

      <main className="max-w-5xl mx-auto px-5 md:px-8 py-14 md:py-20">
        <div className="max-w-2xl">
          <h1 className="text-[2.6rem] md:text-6xl leading-[1.04] text-foreground">{t("safety.title")}</h1>
          <p className="mt-5 text-lg text-muted-foreground leading-relaxed">{t("safety.sub")}</p>
        </div>

        <ul className="mt-12 grid sm:grid-cols-2 border-t border-border">
          {cards.map((section, i) => (
            <li
              key={i}
              className={`py-7 sm:pr-8 border-b border-border ${i % 2 === 1 ? "sm:pl-8 sm:border-l" : ""}`}
            >
              <section.icon className="w-6 h-6 text-secondary" strokeWidth={1.8} />
              <h2 className="mt-3 text-[1.4rem] leading-snug text-foreground">{section.title}</h2>
              <p className="mt-2 text-muted-foreground leading-relaxed">{section.desc}</p>
            </li>
          ))}
        </ul>

        {/* İpuçları: bir öğrencinin defterine not alacağı türden */}
        <aside className="mt-12 max-w-2xl paper-ruled rounded-xl border border-border">
          <h2 className="font-display text-xl font-semibold text-foreground">{t("safety.tipsTitle")}</h2>
          <p className="text-[15px] text-foreground">{t("safety.tips")}</p>
        </aside>
      </main>

      <footer className="border-t border-border">
        <div className="max-w-5xl mx-auto px-5 md:px-8 py-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <Wordmark size="sm" />
          <p className="text-sm text-muted-foreground">© 2026 {BRAND}. {t("safety.rights")}</p>
        </div>
      </footer>
    </div>
  );
};

export default Safety;
