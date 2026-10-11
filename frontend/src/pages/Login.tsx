import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { loginWithPassword, requestOtp, verifyOtp } from "@/lib/api";
import PasswordInput from "@/components/PasswordInput";
import SiteBar from "@/components/layout/SiteBar";
import { useI18n } from "@/i18n";

type Mode = "password" | "otp";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const emailValid = email.includes("@");

  const finish = (token: string, user: Parameters<typeof login>[1]) => {
    login(token, user);
    toast.success(t("login.greet", { name: user.name ? `, ${user.name}` : "" }));
    navigate("/swipe");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailValid) {
      toast.error(t("login.invalidEmail"));
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
          toast.info(t("login.devCode", { code: res.dev_code }), { duration: 20000 });
        } else {
          toast.success(t("login.codeSent"), {
            description: t("login.codeSentDesc"),
            duration: 8000,
          });
        }
      } else {
        const { token, user } = await verifyOtp(email, code);
        finish(token, user);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("common.error"));
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
    ? t("login.busy")
    : mode === "password"
      ? t("login.submitLogin")
      : codeSent
        ? t("login.submitVerify")
        : t("login.submitSendCode");

  const submitDisabled =
    busy ||
    !emailValid ||
    (mode === "password" && password.length === 0) ||
    (mode === "otp" && codeSent && code.length !== 6);

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <SiteBar />

      <div className="flex-1 flex items-start sm:items-center justify-center px-5 py-12 sm:py-16">
        <div className="w-full max-w-sm space-y-7">
          <div className="space-y-2">
            <h1 className="text-[2.5rem] leading-[1.05] text-foreground">{t("login.welcome")}</h1>
            <p className="text-muted-foreground">
              {t(mode === "password" ? "login.subPassword" : "login.subOtp")}
            </p>
          </div>

          {/* Mod seçici: iki sekme, altı çizili olan açık */}
          <div className="flex border-b border-border" role="tablist">
            {([
              { key: "password", label: t("login.tabPassword") },
              { key: "otp", label: t("login.tabOtp") },
            ] as const).map(m => (
              <button
                key={m.key}
                type="button"
                role="tab"
                aria-selected={mode === m.key}
                onClick={() => switchMode(m.key)}
                className={`relative flex-1 pb-3 text-[15px] font-semibold transition-colors ${
                  mode === m.key ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {m.label}
                {mode === m.key && <span className="absolute -bottom-px inset-x-0 h-[3px] bg-foreground" />}
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
                placeholder={t("login.emailPlaceholder")}
                autoComplete="email"
                disabled={mode === "otp" && codeSent}
                aria-label={t("login.emailPlaceholder")}
                className="w-full h-12 pl-12 pr-4 bg-card border border-input rounded-xl text-foreground placeholder:text-muted-foreground/80 outline-none hover:border-foreground/30 focus:border-secondary focus:ring-[3px] focus:ring-secondary/20 transition-colors disabled:opacity-60"
              />
            </div>

            {mode === "password" && (
              <PasswordInput
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={t("login.passwordPlaceholder")}
                autoComplete="current-password"
                aria-label={t("login.passwordPlaceholder")}
                className="h-12 text-base"
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
                  placeholder={t("login.codePlaceholder")}
                  autoFocus
                  aria-label={t("login.codePlaceholder")}
                  className="w-full h-12 pl-12 pr-4 bg-card border border-input rounded-xl text-foreground placeholder:text-muted-foreground/80 placeholder:tracking-normal placeholder:font-normal outline-none focus:border-secondary focus:ring-[3px] focus:ring-secondary/20 transition-colors tracking-[0.3em] font-bold"
                />
              </div>
            )}

            <Button
              type="submit"
              disabled={submitDisabled}
              size="lg"
              className="w-full h-12 text-base"
            >
              {submitLabel}
            </Button>

            {mode === "otp" && codeSent && (
              <button
                type="button"
                onClick={() => { setCodeSent(false); setCode(""); }}
                className="text-[13px] text-muted-foreground hover:text-foreground underline-offset-4 hover:underline transition-colors"
              >
                {t("login.resend")}
              </button>
            )}
            {mode === "password" && (
              <button
                type="button"
                onClick={() => switchMode("otp")}
                className="text-[13px] text-muted-foreground hover:text-foreground underline-offset-4 hover:underline transition-colors"
              >
                {t("login.forgot")}
              </button>
            )}
          </form>

          <div className="pt-2 border-t border-border">
            <p className="pt-5 text-[15px] text-muted-foreground">
              {t("login.noAccount")}{" "}
              <button onClick={() => navigate("/onboarding")} className="text-secondary font-semibold underline-offset-4 hover:underline">
                {t("login.signupLink")}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
