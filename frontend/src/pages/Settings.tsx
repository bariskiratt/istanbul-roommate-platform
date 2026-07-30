import { useNavigate } from "react-router-dom";
import { ArrowLeft, Bell, Lock, User, LogOut, ChevronRight } from "lucide-react";
import BottomNav from "@/components/layout/BottomNav";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

const Settings = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const items = [
    { icon: User, label: "Hesap Bilgileri", action: () => toast("Bu sayfa yakında geliyor") },
    { icon: Bell, label: "Bildirim Ayarları", action: () => toast("Bu sayfa yakında geliyor") },
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
