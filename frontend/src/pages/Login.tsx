import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Home, Mail, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { loginWithPassword, requestOtp, verifyOtp } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";

type Mode = "password" | "otp";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const emailValid = email.includes("@");

  const finish = (token: string, user: Parameters<typeof login>[1]) => {
    login(token, user);
    toast.success(`Hoş geldin${user.name ? `, ${user.name}` : ""}!`);
    navigate("/swipe");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailValid) {
      toast.error("Geçerli bir e-posta adresi girin");
      return;
    }
    setBusy(true);
    try {
      if (mode === "password") {
        const { token, user } = await loginWithPassword(email, password);
        finish(token, user);
      } else if (!codeSent) {
        const res = await requestOtp(email);
        setCodeSent(true);
        // E-posta servisi bağlanana kadar kod dev modda yanıtla gelebilir.
        if (res.dev_code) {
          toast.info(`Giriş kodun: ${res.dev_code}`, { duration: 20000 });
        } else {
          toast.success("Giriş kodu e-postana gönderildi!");
        }
      } else {
        const { token, user } = await verifyOtp(email, code);
        finish(token, user);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Bir şeyler ters gitti");
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    setCode("");
    setCodeSent(false);
  };

  const submitLabel = busy
    ? "Bekleyin..."
    : mode === "password"
      ? "Giriş Yap"
      : codeSent
        ? "Kodu Doğrula"
        : "Giriş Kodu Gönder";

  const submitDisabled =
    busy ||
    !emailValid ||
    (mode === "password" && password.length === 0) ||
    (mode === "otp" && codeSent && code.length !== 6);

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
            <h1 className="text-2xl font-extrabold text-foreground">Tekrar hoş geldin</h1>
            <p className="text-sm text-muted-foreground">
              {mode === "password"
                ? "E-posta ve şifrenle giriş yap"
                : "E-postana tek kullanımlık kod gönderelim"}
            </p>
          </div>

          {/* Mod seçici */}
          <div className="flex rounded-2xl border border-border overflow-hidden">
            {([
              { key: "password", label: "Şifre ile" },
              { key: "otp", label: "Kodla gir" },
            ] as const).map(m => (
              <button
                key={m.key}
                type="button"
                onClick={() => switchMode(m.key)}
                className={`flex-1 py-3 text-sm font-semibold transition-all ${
                  mode === m.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-card text-foreground hover:bg-muted"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground z-10" />
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="öğrenci@üniversite.edu.tr"
                autoComplete="email"
                disabled={mode === "otp" && codeSent}
                className="w-full h-14 pl-12 pr-4 bg-card border border-border rounded-2xl text-foreground placeholder:text-muted-foreground/60 outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all disabled:opacity-60"
              />
            </div>

            {mode === "password" && (
              <PasswordInput
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Şifren"
                autoComplete="current-password"
                className="h-14 text-base rounded-2xl bg-card border-border"
              />
            )}

            {mode === "otp" && codeSent && (
              <div className="relative">
                <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground z-10" />
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
              disabled={submitDisabled}
              className="w-full h-14 bg-primary text-primary-foreground rounded-2xl font-bold text-base disabled:opacity-50"
            >
              {submitLabel}
            </Button>

            {mode === "otp" && codeSent && (
              <button
                type="button"
                onClick={() => { setCodeSent(false); setCode(""); }}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Kodu tekrar gönder / e-postayı değiştir
              </button>
            )}
            {mode === "password" && (
              <button
                type="button"
                onClick={() => switchMode("otp")}
                className="w-full text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Şifreni mi unuttun? Kodla gir →
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
