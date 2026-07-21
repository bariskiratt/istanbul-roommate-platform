import { useNavigate } from "react-router-dom";
import { Shield, ShieldCheck, MessageCircle, Eye, Home } from "lucide-react";
import { Button } from "@/components/ui/button";

const Safety = () => {
  const navigate = useNavigate();

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
          <Button onClick={() => navigate("/onboarding")} className="bg-primary text-primary-foreground rounded-full text-sm font-bold px-5">
            Hemen Başla
          </Button>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-16 space-y-16">
        <div className="text-center space-y-4">
          <div className="w-20 h-20 rounded-3xl bg-primary/10 flex items-center justify-center mx-auto">
            <Shield className="w-10 h-10 text-primary" />
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground">Güvenliğiniz Önceliğimiz</h1>
          <p className="text-muted-foreground max-w-xl mx-auto">RoomMatch olarak kullanıcılarımızın güvenliğini en üst düzeyde tutuyoruz.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-10">
          {[
            {
              icon: ShieldCheck,
              title: ".edu.tr Doğrulama",
              desc: "Sadece doğrulanmış üniversite e-posta adresine sahip öğrenciler kayıt olabilir. Her hesap tek bir .edu.tr adresiyle eşleştirilir, sahte profillerin önüne geçilir."
            },
            {
              icon: Eye,
              title: "İçerik Moderasyonu",
              desc: "Tüm ilanlar ve mesajlar yapay zeka destekli moderasyon sistemimiz tarafından kontrol edilir. Uygunsuz içerikler anında kaldırılır."
            },
            {
              icon: MessageCircle,
              title: "Güvenli Mesajlaşma",
              desc: "Eşleşme olmadan mesajlaşma mümkün değildir. Tüm mesajlar şifrelenmiş olarak iletilir ve kişisel bilgileriniz korunur."
            },
          ].map((section, i) => (
            <div key={i} className="text-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto">
                <section.icon className="w-7 h-7 text-primary" />
              </div>
              <h3 className="text-lg font-bold text-foreground">{section.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{section.desc}</p>
            </div>
          ))}
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
          <p className="text-xs text-muted-foreground">© 2025 RoomMatch. Tüm hakları saklıdır.</p>
        </div>
      </footer>
    </div>
  );
};

export default Safety;
