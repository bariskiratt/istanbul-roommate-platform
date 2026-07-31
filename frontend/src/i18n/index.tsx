import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { translations, type TranslationKey } from "./translations";

export type Lang = "tr" | "en";

const STORAGE_KEY = "lang";
const LOCALES: Record<Lang, string> = { tr: "tr-TR", en: "en-US" };

/** Tarayıcı dili Türkçe değilse İngilizce açılır; seçim kalıcıdır. */
const detectLang = (): Lang => {
  if (typeof window === "undefined") return "tr";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (saved === "tr" || saved === "en") return saved;
  return navigator.language?.toLowerCase().startsWith("tr") ? "tr" : "en";
};

interface I18nValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Çeviri; {isim} yer tutucuları vars ile doldurulur. */
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string;
  /** Dile göre sayı biçimi (12.500 ↔ 12,500). */
  n: (value: number) => string;
  locale: string;
}

const I18nContext = createContext<I18nValue | null>(null);

export const I18nProvider = ({ children }: { children: React.ReactNode }) => {
  const [lang, setLangState] = useState<Lang>(detectLang);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    window.localStorage.setItem(STORAGE_KEY, l);
    setLangState(l);
  }, []);

  const value = useMemo<I18nValue>(() => {
    const locale = LOCALES[lang];
    const numberFormat = new Intl.NumberFormat(locale);
    return {
      lang,
      setLang,
      locale,
      n: (v: number) => numberFormat.format(v),
      t: (key, vars) => {
        // Anahtar eksikse Türkçe'ye, o da yoksa anahtarın kendisine düşer —
        // eksik çeviri arayüzü boş bırakmaz.
        const raw = translations[lang][key] ?? translations.tr[key] ?? key;
        if (!vars) return raw;
        return raw.replace(/\{(\w+)\}/g, (m, name) =>
          name in vars ? String(vars[name]) : m,
        );
      },
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
};

export const useI18n = (): I18nValue => {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n, I18nProvider içinde kullanılmalı.");
  return ctx;
};
