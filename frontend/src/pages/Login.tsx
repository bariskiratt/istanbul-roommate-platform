import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError, loginWithPassword, needsSecondFactor, requestOtp, resetPassword, verifyOtp } from "@/lib/api";
import { profileIncomplete } from "@/lib/onboardingDraft";
import PasswordInput from "@/components/PasswordInput";
import NewPasswordFields from "@/components/NewPasswordFields";
import { newPasswordReady } from "@/lib/password";
import SiteBar from "@/components/layout/SiteBar";
import { useI18n } from "@/i18n";

// "reset": şifresini unutan kullanıcı e-postasına gelen kodla yeni şifre
// koyar ve oturum açar. Eskiden "şifreni mi unuttun" yalnızca kodla girişe
// götürüyordu; kişi içeride şifresini değiştiremiyor, hesabını silemiyordu.
type Mode = "password" | "otp" | "reset";

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  // Yönetici hesabı iki adımlıdır: şifre VE e-posta kodu birlikte istenir.
  // Şifre sekmesinde şifre kabul edilince kod alanı açılır (adminStep); kod
  // sekmesinde sunucu şifreyi isteyince şifre alanı açılır (needPassword).
  const [adminStep, setAdminStep] = useState(false);
  const [needPassword, setNeedPassword] = useState(false);
  const [busy, setBusy] = useState(false);

  const emailValid = email.includes("@");

  const finish = (token: string, user: Parameters<typeof login>[1], message?: string) => {
    login(token, user);
    toast.success(message ?? t("login.greet", { name: user.name ? `, ${user.name}` : "" }));
    // Kaydı yarıda kalan hesap (ör. kod doğrulandıktan sonra sekme kapandı)
    // boş profille uygulamaya değil, kaydın profil adımlarına döner.
    navigate(profileIncomplete(user) ? "/onboarding" : "/swipe");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailValid) {
      toast.error(t("login.invalidEmail"));
      return;
    }
    setBusy(true);
    try {
      if (mode === "reset" && codeSent) {
        const { token, user } = await resetPassword(email, code, newPassword);
        finish(token, user, t("login.resetDone"));
      } else if (mode === "password" && adminStep) {
        const { token, user } = await verifyOtp(email, code, password);
        finish(token, user);
      } else if (mode === "password") {
        const res = await loginWithPassword(email, password);
        if (needsSecondFactor(res)) {
          setAdminStep(true);
          if (res.dev_code) {
            toast.info(t("login.devCode", { code: res.dev_code }), { duration: 20000 });
          } else {
            toast.success(t("login.adminCodeSent"), {
              description: t("login.codeSentDesc"),
              duration: 8000,
            });
          }
        } else {
          finish(res.token, res.user);
        }
      } else if (!codeSent) {
        const res = await requestOtp(email);
        setCodeSent(true);
        // E-posta servisi bağlanana kadar kod dev modda yanıtla gelebilir.
        if (res.dev_code) {
          toast.info(t("login.devCode", { code: res.dev_code }), { duration: 20000 });
        } else {
          // API, adres kayıtlı olmasa da aynı yanıtı verir (üyelik sızmasın
          // diye) ve o durumda kod göndermez; açıklama bu yüzden koşullu.
          toast.success(t("login.codeSent"), {
            description: t("login.codeSentLoginDesc"),
            duration: 8000,
          });
        }
      } else {
        try {
          const { token, user } = await verifyOtp(email, code, needPassword ? password : undefined);
          finish(token, user);
        } catch (err) {
          // Yönetici hesabı: kod doğru ama şifre de gerekiyor. Kod harcanmadı,
          // şifre alanı açılır ve aynı kodla tekrar gönderilir.
          if (err instanceof ApiError && err.field === "password" && !needPassword) {
            setNeedPassword(true);
            toast.info(t("login.adminPasswordNeeded"));
            return;
          }
          throw err;
        }
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  const resetCodeStep = () => {
    setCode("");
    setNewPassword("");
    setConfirmPassword("");
    setCodeSent(false);
    setAdminStep(false);
    setNeedPassword(false);
  };

  const switchMode = (next: Mode) => {
    setMode(next);
    resetCodeStep();
  };

  // Kod alanı: kod sekmesinde kod gidince, şifre sekmesinde yönetici adımında.
  const showCode = ((mode === "otp" || mode === "reset") && codeSent) || adminStep;
  const showPassword = mode === "password" || needPassword;
  const showNewPassword = mode === "reset" && codeSent;

  const submitLabel = busy
    ? t("login.busy")
    : mode === "reset"
      ? t(codeSent ? "login.submitReset" : "login.submitSendResetCode")
      : showCode
        ? t("login.submitVerify")
        : mode === "password"
          ? t("login.submitLogin")
          : t("login.submitSendCode");

  const submitDisabled =
    busy ||
    !emailValid ||
    (showPassword && password.length === 0) ||
    (showCode && code.length !== 6) ||
    (showNewPassword && !newPasswordReady(newPassword, confirmPassword));

  const subtitle =
    mode === "reset" ? "login.resetSub" : mode === "password" ? "login.subPassword" : "login.subOtp";

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <SiteBar />

      <div className="flex-1 flex items-start sm:items-center justify-center px-5 py-12 sm:py-16">
        <div className="w-full max-w-sm space-y-7">
          <div className="space-y-2">
            <h1 className="text-[2.5rem] leading-[1.05] text-foreground">
              {t(mode === "reset" ? "login.resetTitle" : "login.welcome")}
            </h1>
            <p className="text-muted-foreground">{t(subtitle)}</p>
          </div>

          {/* Mod seçici: iki sekme, altı çizili olan açık (sıfırlamada gizli) */}
          {mode !== "reset" && (
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
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground z-10" />
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder={t("login.emailPlaceholder")}
                autoComplete="email"
                disabled={showCode}
                aria-label={t("login.emailPlaceholder")}
                className="w-full h-12 pl-12 pr-4 bg-card border border-input rounded-xl text-foreground placeholder:text-muted-foreground/80 outline-none hover:border-foreground/30 focus:border-secondary focus:ring-[3px] focus:ring-secondary/20 transition-colors disabled:opacity-60"
              />
            </div>

            {showPassword && (
              <PasswordInput
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder={t("login.passwordPlaceholder")}
                autoComplete="current-password"
                aria-label={t("login.passwordPlaceholder")}
                disabled={adminStep}
                autoFocus={needPassword}
                className="h-12 text-base"
              />
            )}

            {showCode && (
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

            {showNewPassword && (
              <NewPasswordFields
                next={newPassword}
                confirm={confirmPassword}
                onNextChange={setNewPassword}
                onConfirmChange={setConfirmPassword}
              />
            )}

            <Button
              type="submit"
              disabled={submitDisabled}
              size="lg"
              className="w-full h-12 text-base"
            >
              {submitLabel}
            </Button>

            {showCode && (
              <button
                type="button"
                onClick={resetCodeStep}
                className="text-[13px] text-muted-foreground hover:text-foreground underline-offset-4 hover:underline transition-colors"
              >
                {t("login.resend")}
              </button>
            )}
            {mode === "password" && !adminStep && (
              <button
                type="button"
                onClick={() => switchMode("reset")}
                className="text-[13px] text-muted-foreground hover:text-foreground underline-offset-4 hover:underline transition-colors"
              >
                {t("login.forgot")}
              </button>
            )}
            {mode === "reset" && (
              <button
                type="button"
                onClick={() => switchMode("password")}
                className="block text-[13px] text-muted-foreground hover:text-foreground underline-offset-4 hover:underline transition-colors"
              >
                {t("login.backToLogin")}
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
