import { Check, Circle } from "lucide-react";
import PasswordInput from "@/components/PasswordInput";
import { useI18n } from "@/i18n";

/**
 * Yeni şifre + tekrarı, altında kurallar. Hesap ayarlarındaki şifre
 * değiştirme ve girişteki "şifreni sıfırla" aynı alanları kullanır.
 *
 * Kurallar kayıttakilerle aynı (Onboarding.tsx). Sunucu yalnızca 8 karakteri
 * zorunlu tutuyor; büyük harf ve rakam arayüzün isteği.
 */
export const passwordRules = (pw: string) => ({
  length: pw.length >= 8,
  uppercase: /[A-Z]/.test(pw),
  number: /[0-9]/.test(pw),
});

/** Yeni şifre kurallara uyuyor ve tekrarıyla aynı mı? */
export const newPasswordReady = (next: string, confirm: string) => {
  const r = passwordRules(next);
  return r.length && r.uppercase && r.number && next === confirm;
};

interface Props {
  next: string;
  confirm: string;
  onNextChange: (v: string) => void;
  onConfirmChange: (v: string) => void;
}

const NewPasswordFields = ({ next, confirm, onNextChange, onConfirmChange }: Props) => {
  const { t } = useI18n();
  const rules = passwordRules(next);
  return (
    <>
      <PasswordInput
        value={next}
        onChange={e => onNextChange(e.target.value)}
        placeholder={t("account.newPassword")}
        aria-label={t("account.newPassword")}
        className="h-12"
      />
      {next.length > 0 && (
        <div className="space-y-1">
          {([
            { id: "length", ok: rules.length, key: "ob.ruleLength" },
            { id: "upper", ok: rules.uppercase, key: "ob.ruleUpper" },
            { id: "number", ok: rules.number, key: "ob.ruleNumber" },
          ] as const).map(r => (
            <p key={r.id} className={`text-[13px] flex items-center gap-1.5 ${r.ok ? "text-accent" : "text-muted-foreground"}`}>
              {r.ok ? <Check className="w-3.5 h-3.5" /> : <Circle className="w-3.5 h-3.5" />} {t(r.key)}
            </p>
          ))}
        </div>
      )}
      <PasswordInput
        value={confirm}
        onChange={e => onConfirmChange(e.target.value)}
        placeholder={t("account.repeatPassword")}
        aria-label={t("account.repeatPassword")}
        className="h-12"
      />
      {confirm.length > 0 && next !== confirm && (
        <p className="text-[13px] text-destructive">{t("ob.passwordMismatch")}</p>
      )}
    </>
  );
};

export default NewPasswordFields;
