import { normalizeDealbreakers, type Dealbreaker } from "./dealbreakers";

/**
 * Kayıt formunun yarım kalmış hâli.
 *
 * Kayıt sekiz adım sürüyor ve kullanıcı kodu almak için posta uygulamasına
 * geçiyor; telefon tarayıcısı o arada sekmeyi yeniden yükleyebiliyor.
 * Eskiden her yenileme formu sıfırlıyordu: kod adımındaki kişi e-postayı
 * yeniden yazınca "zaten kayıtlı" hatası alıyor, profil adımlarındaki kişi
 * girdiği her şeyi kaybediyordu.
 *
 * sessionStorage'da durur: yenilemeye dayanır, sekme kapanınca silinir, yani
 * ortak bir bilgisayarda bir sonraki kişiye kalmaz. Sekmesini kapatan kişi
 * yine kaybetmez: girişte profili yarım hesap kayda geri gönderilir (bkz.
 * profileIncomplete). Şifre ve doğrulama kodu BİLEREK yazılmaz.
 */
export interface OnboardingDraft {
  step: number;
  email: string;
  /** Hesabı açılmış adres: aynı adresle ikinci kez register çağrılmaz. */
  registeredEmail: string;
  name: string;
  gender: string;
  birthYear: string;
  department: string;
  year: string;
  budget: number[];
  district: string[];
  lifestyle: { smoking: boolean; alcohol: boolean; pets: boolean; sleep: string };
  /** İstemediklerim; okurken bilinmeyen anahtarlar atılır. */
  dealbreakers: Dealbreaker[];
  photos: string[];
}

const KEY = "onboarding-draft";

export const EMPTY_ONBOARDING_DRAFT: OnboardingDraft = {
  step: 0,
  email: "",
  registeredEmail: "",
  name: "",
  gender: "",
  birthYear: "",
  department: "",
  year: "",
  budget: [4000, 8000],
  district: [],
  lifestyle: { smoking: false, alcohol: false, pets: false, sleep: "esnek" },
  dealbreakers: [],
  photos: [],
};

/** Kayıtlı taslağı okur; okunamayan ya da türü tutmayan alan boş değerine düşer. */
export const loadOnboardingDraft = (): OnboardingDraft => {
  // Derin kopya: dizileri paylaşırsa varsayılanlar formla birlikte değişirdi.
  // (structuredClone eski iOS Safari'de yok; bu veri zaten düz JSON.)
  const draft: OnboardingDraft = JSON.parse(JSON.stringify(EMPTY_ONBOARDING_DRAFT));
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(KEY) ?? "null");
    if (!saved || typeof saved !== "object") return draft;
    for (const key of Object.keys(draft) as (keyof OnboardingDraft)[]) {
      const value = saved[key];
      // Eski bir sürümün yazdığı taslak formu bozmasın: türü tutmayan alan alınmaz.
      if (typeof value === typeof draft[key] && Array.isArray(value) === Array.isArray(draft[key])) {
        (draft as Record<keyof OnboardingDraft, unknown>)[key] = value;
      }
    }
  } catch {
    // Gizli sekme ya da bozuk JSON: boş formla devam edilir.
  }
  // Tür (dizi) tutsa da içerik eski ya da bozuk olabilir; sunucu bilinmeyen
  // anahtarı reddeder ve kayıt son adımda takılırdı.
  draft.dealbreakers = normalizeDealbreakers(draft.dealbreakers);
  return draft;
};

export const saveOnboardingDraft = (draft: OnboardingDraft) => {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    // Depolama kapalıysa form taslaksız da çalışır.
  }
};

export const clearOnboardingDraft = () => {
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    // yok say
  }
};

/**
 * Ad yalnızca kaydın son adımında kaydedilir (profil düzenleme boş adı kabul
 * etmez), yani adı boş hesap kaydı bitirmemiştir.
 */
export const profileIncomplete = (user: { name: string } | null | undefined): boolean =>
  !!user && user.name.trim() === "";
