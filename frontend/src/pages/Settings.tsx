import { useNavigate } from "react-router-dom";
import { ArrowLeft, Lock, User, LogOut, ChevronRight, Sun, Moon, Monitor } from "lucide-react";
import { useTheme } from "next-themes";
import BottomNav from "@/components/layout/BottomNav";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

const themeOptions = [
  { value: "light", label: "Açık", icon: Sun },
  { value: "dark", label: "Koyu", icon: Moon },
  { value: "system", label: "Sistem", icon: Monitor },
] as const;

const Settings = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const { theme, setTheme } = useTheme();

  const items = [
    { icon: User, label: "Hesap Bilgileri", action: () => navigate("/settings/account") },
    { icon: Lock, label: "Gizlilik ve Güvenlik", action: () => navigate("/safety") },
    { icon: LogOut, label: "Çıkış Yap", action: () => { logout(); toast("Çıkış yapıldı"); navigate("/"); }, destructive: true },
  ];

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="sticky top-0 z-50 bg-card/95 backdrop-blur-lg border-b border-border px-6 py-4 flex items-center gap-3">
        <button onClick={() => navigate("/profile")} className="w-10 h-10 rounded-full bg-background flex items-center justify-center text-foreground hover:bg-muted transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold text-foreground">Ayarlar</h1>
      </div>

      <div className="px-6 py-4 space-y-2">
        {/* Tema seçimi */}
        <div className="card-listing p-4 space-y-3">
          <div className="flex items-center gap-4">
            <Sun className="w-5 h-5 text-foreground" />
            <span className="flex-1 text-left font-medium text-sm text-foreground">Görünüm</span>
          </div>
          <div className="flex rounded-xl border border-border overflow-hidden">
            {themeOptions.map(opt => (
              <button
                key={opt.value}
                onClick={() => setTheme(opt.value)}
                className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-all ${
                  theme === opt.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-card text-foreground hover:bg-muted"
                }`}
              >
                <opt.icon className="w-3.5 h-3.5" />
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {items.map((item, i) => (
          <button
            key={i}
            onClick={item.action}
            className={`w-full card-listing p-4 flex items-center gap-4 hover:shadow-md transition-shadow ${item.destructive ? 'text-destructive' : 'text-foreground'}`}
          >
            <item.icon className="w-5 h-5" />
            <span className="flex-1 text-left font-medium text-sm">{item.label}</span>
            <ChevronRight className="w-4 h-4 text-muted-foreground" />
          </button>
        ))}
      </div>

      <BottomNav />
    </div>
  );
};

export default Settings;
