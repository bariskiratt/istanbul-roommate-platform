import { useNavigate } from "react-router-dom";
import { Lock, User, LogOut, ChevronRight, Sun, Moon, Monitor, ShieldAlert } from "lucide-react";
import { useTheme } from "next-themes";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n, type Lang } from "@/i18n";

const Settings = () => {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const { theme, setTheme } = useTheme();
  const { t, lang, setLang } = useI18n();

  const themeOptions = [
    { value: "light", label: t("settings.light"), icon: Sun },
    { value: "dark", label: t("settings.dark"), icon: Moon },
    { value: "system", label: t("settings.system"), icon: Monitor },
  ] as const;

  const langOptions: { value: Lang; label: string }[] = [
    { value: "tr", label: "Türkçe" },
    { value: "en", label: "English" },
  ];

  // Moderasyon paneli yalnızca yöneticiye görünür. Alt menüye değil buraya
  // konuldu: alt menü yöneticide zaten 6 sekmeye çıkıyor, 7.'si dar ekranda
  // taşıyor (bkz. BottomNav.tsx notu).
  const items: {
    icon: typeof User;
    label: string;
    action: () => void;
    destructive?: boolean;
  }[] = [
    ...(user?.is_admin
      ? [{ icon: ShieldAlert, label: t("settings.moderation"), action: () => navigate("/admin") }]
      : []),
    { icon: User, label: t("settings.account"), action: () => navigate("/settings/account") },
    // Bu bağlantı /safety'ye gidiyordu: kullanıcı gizlilik politikası bekleyip
    // güvenlik ipuçları buluyordu.
    { icon: Lock, label: t("settings.privacy"), action: () => navigate("/privacy") },
    {
      icon: LogOut,
      label: t("settings.logout"),
      action: () => { logout(); toast(t("settings.loggedOut")); navigate("/"); },
      destructive: true,
    },
  ];

  // Seçili seçenek mürekkeple dolar; Onboarding'deki seçimlerle aynı dil.
  const segment = (selected: boolean) =>
    `flex-1 h-11 text-[14px] font-semibold flex items-center justify-center gap-1.5 transition-colors ${
      selected ? "bg-foreground text-background" : "bg-card text-foreground hover:bg-muted"
    }`;

  return (
    <div className="min-h-screen bg-background pb-24">
      <AppHeader title={t("settings.title")} showBack onBack={() => navigate("/profile")} hideControls />

      <div className="px-5 py-6 space-y-8 max-w-lg mx-auto">
        {/* Tema seçimi */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("settings.appearance")}</h2>
          <div className="flex rounded-xl border border-input overflow-hidden divide-x divide-input" role="radiogroup" aria-label={t("settings.appearance")}>
            {themeOptions.map(opt => (
              <button
                key={opt.value}
                role="radio"
                aria-checked={theme === opt.value}
                onClick={() => setTheme(opt.value)}
                className={segment(theme === opt.value)}
              >
                <opt.icon className="w-4 h-4" />
                {opt.label}
              </button>
            ))}
          </div>
        </section>

        {/* Dil seçimi */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("settings.language")}</h2>
          <div className="flex rounded-xl border border-input overflow-hidden divide-x divide-input" role="radiogroup" aria-label={t("settings.language")}>
            {langOptions.map(opt => (
              <button
                key={opt.value}
                role="radio"
                aria-checked={lang === opt.value}
                onClick={() => setLang(opt.value)}
                className={segment(lang === opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </section>

        <nav className="rounded-2xl border border-border divide-y divide-border overflow-hidden">
          {items.map((item, i) => (
            <button
              key={i}
              onClick={item.action}
              className={`w-full px-4 h-14 flex items-center gap-4 hover:bg-muted transition-colors ${item.destructive ? "text-destructive" : "text-foreground"}`}
            >
              <item.icon className="w-5 h-5" />
              <span className="flex-1 text-left font-semibold text-[15px]">{item.label}</span>
              {!item.destructive && <ChevronRight className="w-4 h-4 text-muted-foreground" />}
            </button>
          ))}
        </nav>
      </div>

      <BottomNav />
    </div>
  );
};

export default Settings;
