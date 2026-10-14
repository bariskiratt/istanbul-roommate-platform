/**
 * Arayüzün şifre kuralları: kayıt (Onboarding), şifre değiştirme ve şifre
 * sıfırlama aynı kuralı kullanır. Sunucu yalnızca 8 karakteri zorunlu
 * tutuyor; büyük harf ve rakam arayüzün isteği.
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
