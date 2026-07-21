import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Home, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@")) {
      toast.error("Geçerli bir e-posta adresi girin");
      return;
    }
    toast.success("Giriş kodu e-postanıza gönderildi!");
    // Simulate OTP success — login and redirect
    setTimeout(() => {
      login();
      navigate("/swipe");
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-card/95 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <button onClick={() => navigate("/")} className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-lg text-foreground tracking-tight">RoomMatch</span>
          </button>
        </div>
      </nav>

      <div className="flex-1 flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm space-y-8">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center mx-auto">
              <Home className="w-7 h-7 text-primary-foreground" />
            </div>
            <h1 className="text-2xl font-extrabold text-foreground">Üniversite e-postanla giriş yap</h1>
            <p className="text-sm text-muted-foreground">Sadece .edu.tr uzantılı e-postalar kabul edilir</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="öğrenci@üniversite.edu.tr"
                className="w-full h-14 pl-12 pr-4 bg-card border border-border rounded-2xl text-foreground placeholder:text-muted-foreground/60 outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
              />
            </div>
            <Button type="submit" className="w-full h-14 bg-primary text-primary-foreground rounded-2xl font-bold text-base">
              Giriş Kodu Gönder
            </Button>
          </form>

          <div className="text-center">
            <p className="text-sm text-muted-foreground">
              Hesabın yok mu?{" "}
              <button onClick={() => navigate("/onboarding")} className="text-primary font-semibold hover:underline">
                Kayıt ol →
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
