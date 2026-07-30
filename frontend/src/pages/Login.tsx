import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Home, Mail, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { requestOtp, verifyOtp } from "@/lib/api";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.includes("@")) {
      toast.error("Geçerli bir e-posta adresi girin");
      return;
    }
    setBusy(true);
    try {
      if (!codeSent) {
        const res = await requestOtp(email);
        setCodeSent(true);
        // E-posta servisi bağlanana kadar kod dev modda yanıtla gelir.
        if (res.dev_code) {
          toast.info(`Giriş kodun: ${res.dev_code}`, { duration: 20000 });
        } else {
          toast.success("Giriş kodu e-postana gönderildi!");
        }
      } else {
        const { token, user } = await verifyOtp(email, code);
        login(token, user);
        toast.success(`Hoş geldin${user.name ? `, ${user.name}` : ""}!`);
        navigate("/swipe");
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bir şeyler ters gitti");
    } finally {
      setBusy(false);
    }
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
                disabled={codeSent}
                className="w-full h-14 pl-12 pr-4 bg-card border border-border rounded-2xl text-foreground placeholder:text-muted-foreground/60 outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all disabled:opacity-60"
              />
            </div>
            {codeSent && (
              <div className="relative">
                <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={e => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="6 haneli kod"
                  autoFocus
                  className="w-full h-14 pl-12 pr-4 bg-card border border-border rounded-2xl text-foreground placeholder:text-muted-foreground/60 outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all tracking-[0.3em] font-bold"
                />
              </div>
            )}
            <Button
              type="submit"
              disabled={busy || (codeSent && code.length !== 6)}
              className="w-full h-14 bg-primary text-primary-foreground rounded-2xl font-bold text-base disabled:opacity-50"
            >
              {busy ? "Bekleyin..." : codeSent ? "Giriş Yap" : "Giriş Kodu Gönder"}
            </Button>
            {codeSent && (
              <button
                type="button"
                onClick={() => { setCodeSent(false); setCode(""); }}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Farklı e-posta kullan
              </button>
            )}
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
