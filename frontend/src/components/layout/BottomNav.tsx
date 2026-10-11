import { Home, Heart, MessageCircle, User, Map, Building2 } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";

// Not: /notifications kaldırıldı — Beğeniler ile birebir aynı veriyi
// gösteriyordu. Yerine uygulama içinden erişilemeyen Bütçe Haritası girdi.
//
// Not (moderasyon paneli): /admin bilerek buraya EKLENMEDİ. Yöneticide menü
// zaten 6 sekmeye çıkıyor; 320 px genişlikte (px-6 kenar boşluğuyla 272 px)
// 7. sekme başına ~39 px düşer ve 10 px'lik etiketler ("Mesajlar", "Yönetim")
// sığmayıp taşar. Panel girişi Ayarlar'da (Settings.tsx), yalnızca yöneticide.
const navItems: { icon: typeof Home; labelKey: TranslationKey; path: string; adminOnly?: boolean }[] = [
  { icon: Home, labelKey: "nav.discover", path: "/swipe" },
  { icon: Heart, labelKey: "nav.likes", path: "/matches" },
  // Evler yalnızca yöneticiye görünür (adminOnly)
  { icon: Building2, labelKey: "nav.houses", path: "/listings", adminOnly: true },
  { icon: Map, labelKey: "nav.map", path: "/explore" },
  { icon: MessageCircle, labelKey: "nav.messages", path: "/messages" },
  { icon: User, labelKey: "nav.profile", path: "/profile" },
];

const BottomNav = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { t } = useI18n();
  const items = navItems.filter(i => !i.adminOnly || user?.is_admin);

  // Hinge'in koyu sekme çubuğu: açık temada mürekkep, koyu temada tahta.
  // Açık sekmenin altında fosforlu kalemden kısa bir çizgi var.
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-primary text-primary-foreground dark:bg-card dark:text-foreground dark:border-t dark:border-border">
      <div className="max-w-lg mx-auto flex justify-around items-center pt-2.5 pb-[max(0.6rem,env(safe-area-inset-bottom))] px-4">
        {items.map((item) => {
          const isActive = location.pathname === item.path ||
            (item.path === "/messages" && location.pathname.startsWith("/chat"));
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              aria-current={isActive ? "page" : undefined}
              className={`flex flex-col items-center gap-1 min-w-[3.25rem] transition-opacity duration-150 ${
                isActive ? "opacity-100" : "opacity-60 hover:opacity-90"
              }`}
            >
              <item.icon className="w-[22px] h-[22px]" strokeWidth={isActive ? 2.4 : 1.8} />
              <span className={`text-[11px] leading-none ${isActive ? "font-semibold" : ""}`}>
                {t(item.labelKey)}
              </span>
              <span className={`h-[3px] w-5 rounded-full ${isActive ? "bg-highlighter" : "bg-transparent"}`} aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNav;
