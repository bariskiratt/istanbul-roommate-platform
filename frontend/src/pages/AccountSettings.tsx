import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Mail, GraduationCap, ShieldCheck, Calendar, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import PasswordInput from "@/components/PasswordInput";
import NewPasswordFields, { newPasswordReady } from "@/components/NewPasswordFields";
import BottomNav from "@/components/layout/BottomNav";
import AppHeader from "@/components/layout/AppHeader";
import { useAuth } from "@/contexts/AuthContext";
import { changePassword, deleteAccount, requestOtp, resetPassword } from "@/lib/api";
import { parseUtc } from "@/lib/date";
import { useI18n } from "@/i18n";

const AccountSettings = () => {
  const navigate = useNavigate();
  const { user: me, login, logout } = useAuth();
  const { t, locale } = useI18n();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  // Mevcut şifresini hatırlamayan (ör. kodla girmiş) kullanıcı, şifre yerine
  // e-postasına gelen kodla da değiştirebilir ve hesabını silebilir. Eskiden
  // iki işlem de mevcut şifreyi istiyordu; şifresini unutan kişinin hesabını
  // silmesinin tek yolu kurucuya yazmaktı.
  const [pwCode, setPwCode] = useState<string | null>(null);
  const [sendingCode, setSendingCode] = useState(false);

  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteCode, setDeleteCode] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  if (!me) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">{t("account.loginRequired")}</p>
      </div>
    );
  }

  const usingCode = pwCode !== null;
  const canSave =
    (usingCode ? pwCode.length === 6 : current.length > 0) && newPasswordReady(next, confirm);

  /** Kayıtlı adrese tek kullanımlık kod yollar; başarılıysa true. */
  const sendCode = async (): Promise<boolean> => {
    setSendingCode(true);
    try {
      const res = await requestOtp(me.email);
      if (res.dev_code) {
        toast.info(t("login.devCode", { code: res.dev_code }), { duration: 20000 });
      } else {
        toast.success(t("account.codeSent", { email: me.email }), {
          description: t("login.codeSentDesc"),
          duration: 8000,
        });
      }
      return true;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("common.error"));
      return false;
    } finally {
      setSendingCode(false);
    }
  };

  const submitPassword = async () => {
    setSaving(true);
    try {
      if (usingCode) {
        // Sunucu bütün oturumları kapatır ve bu cihaz için yenisini verir:
        // kullanıcı burada kalır, diğer cihazlardan çıkar.
        const { token, user } = await resetPassword(me.email, pwCode, next);
        login(token, user);
        toast.success(t("account.passwordUpdated"), {
          description: t("account.passwordResetDesc"),
        });
        setPwCode(null);
        setNext("");
        setConfirm("");
        return;
      }
      await changePassword(current, next);
      toast.success(t("account.passwordUpdated"), {
        description: t("account.passwordUpdatedDesc"),
      });
      logout();
      navigate("/login");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("account.passwordFailed"));
    } finally {
      setSaving(false);
    }
  };

  const submitDelete = async () => {
    setDeleting(true);
    try {
      await deleteAccount(deleteCode !== null ? { code: deleteCode } : { password: deletePassword });
      toast.success(t("account.deleted"));
      logout();
      navigate("/");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("account.deleteFailed"));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background pb-24">
      <AppHeader title={t("settings.account")} showBack onBack={() => navigate("/settings")} hideControls />

      <div className="px-5 py-6 space-y-10 max-w-lg mx-auto">
        {/* Hesap özeti — değiştirilemeyen doğrulanmış alanlar */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("account.sectionYours")}</h2>
          <div className="rounded-2xl border border-border divide-y divide-border">
            {[
              { id: "email", icon: Mail, label: t("profile.fieldEmail"), value: me.email },
              {
                id: "university",
                icon: GraduationCap,
                label: t("account.fieldUniversity"),
                value: me.university ?? t("ob.universityUnknown"),
              },
              {
                id: "member",
                icon: Calendar,
                label: t("profile.statMember"),
                value: parseUtc(me.created_at).toLocaleDateString(locale, {
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                }),
              },
            ].map(row => (
              <div key={row.id} className="flex items-center gap-3 p-4">
                <row.icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <div className="min-w-0">
                  <p className="text-[12px] text-muted-foreground">{row.label}</p>
                  <p className="text-[15px] text-foreground truncate">{row.value}</p>
                </div>
              </div>
            ))}
          </div>
          {/* Cümle parçalanmasın diye açıklama tek metin, bağlantı ayrı satırda:
              İngilizce'de kelime sırası Türkçe'den farklı. */}
          <p className="text-[13px] text-muted-foreground leading-relaxed flex items-start gap-2">
            <ShieldCheck className="w-4 h-4 mt-0.5 flex-shrink-0 text-accent" />
            <span>
              {t("account.identityNote")} {t("account.profileHint")}
            </span>
          </p>
          <button
            onClick={() => navigate("/profile/edit")}
            className="text-[13px] font-semibold text-secondary hover:underline"
          >
            {t("pedit.title")}
          </button>
        </section>

        {/* Şifre değiştirme */}
        <section className="space-y-3">
          <h2 className="text-xl text-foreground">{t("account.changePassword")}</h2>
          {usingCode ? (
            <CodeInput value={pwCode} onChange={setPwCode} />
          ) : (
            <PasswordInput
              value={current}
              onChange={e => setCurrent(e.target.value)}
              placeholder={t("account.currentPassword")}
              aria-label={t("account.currentPassword")}
              autoComplete="current-password"
              className="h-12"
            />
          )}
          <NewPasswordFields
            next={next}
            confirm={confirm}
            onNextChange={setNext}
            onConfirmChange={setConfirm}
          />
          <Button
            onClick={submitPassword}
            disabled={!canSave || saving}
            size="lg"
            className="w-full h-12 text-base disabled:opacity-40"
          >
            {t(saving ? "common.saving" : "account.updatePassword")}
          </Button>
          <button
            type="button"
            disabled={sendingCode}
            onClick={async () => {
              if (usingCode) {
                setPwCode(null);
              } else if (await sendCode()) {
                setPwCode("");
              }
            }}
            className="text-[13px] font-semibold text-secondary hover:underline disabled:opacity-50"
          >
            {t(usingCode ? "account.useCurrentPassword" : "account.forgotCurrent")}
          </button>
          <p className="text-[13px] text-muted-foreground leading-relaxed">{t("account.passwordNote")}</p>
        </section>

        {/* Tehlikeli bölge */}
        <section className="space-y-3">
          <h2 className="text-xl text-destructive">{t("account.deleteTitle")}</h2>
          <div className="rounded-2xl border border-destructive/40 p-4 space-y-3">
            <p className="text-[14px] text-muted-foreground leading-relaxed">{t("account.deleteDesc")}</p>
            {!deleteOpen ? (
              <Button
                variant="outline"
                onClick={() => setDeleteOpen(true)}
                className="w-full h-11 border-destructive/50 text-destructive hover:bg-destructive hover:text-destructive-foreground"
              >
                {t("account.deleteStart")}
              </Button>
            ) : (
              <div className="space-y-3">
                {deleteCode !== null ? (
                  <CodeInput value={deleteCode} onChange={setDeleteCode} />
                ) : (
                  <PasswordInput
                    value={deletePassword}
                    onChange={e => setDeletePassword(e.target.value)}
                    placeholder={t("account.deletePasswordPlaceholder")}
                    aria-label={t("account.deletePasswordPlaceholder")}
                    autoComplete="current-password"
                    className="h-12"
                  />
                )}
                <button
                  type="button"
                  disabled={sendingCode}
                  onClick={async () => {
                    if (deleteCode !== null) {
                      setDeleteCode(null);
                    } else if (await sendCode()) {
                      setDeleteCode("");
                    }
                  }}
                  className="text-[13px] font-semibold text-secondary hover:underline disabled:opacity-50"
                >
                  {t(deleteCode !== null ? "account.useCurrentPassword" : "account.deleteWithCode")}
                </button>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => { setDeleteOpen(false); setDeletePassword(""); setDeleteCode(null); }}
                    className="flex-1 h-11"
                  >
                    {t("common.cancel")}
                  </Button>
                  <Button
                    onClick={submitDelete}
                    disabled={(deleteCode !== null ? deleteCode.length !== 6 : deletePassword.length === 0) || deleting}
                    variant="destructive"
                    className="flex-1 h-11 disabled:opacity-50"
                  >
                    {t(deleting ? "account.deleting" : "account.deleteConfirm")}
                  </Button>
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      <BottomNav />
    </div>
  );
};

/** E-postaya gelen 6 haneli kod alanı (yalnızca rakam). */
const CodeInput = ({ value, onChange }: { value: string; onChange: (v: string) => void }) => {
  const { t } = useI18n();
  return (
    <div className="relative">
      <KeyRound className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground z-10" />
      <input
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={value}
        onChange={e => onChange(e.target.value.replace(/\D/g, ""))}
        placeholder={t("login.codePlaceholder")}
        aria-label={t("login.codePlaceholder")}
        autoFocus
        className="w-full h-12 pl-12 pr-4 bg-card border border-input rounded-xl text-foreground placeholder:text-muted-foreground/80 placeholder:tracking-normal placeholder:font-normal outline-none focus:border-secondary focus:ring-[3px] focus:ring-secondary/20 transition-colors tracking-[0.3em] font-bold"
      />
    </div>
  );
};

export default AccountSettings;
