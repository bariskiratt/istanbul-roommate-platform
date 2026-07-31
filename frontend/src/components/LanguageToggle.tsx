import { useI18n } from "@/i18n";

/** TR / EN geçişi — seçim localStorage'da saklanır. */
const LanguageToggle = ({ className = "" }: { className?: string }) => {
  const { lang, setLang, t } = useI18n();
  const next = lang === "tr" ? "en" : "tr";

  return (
    <button
      onClick={() => setLang(next)}
      aria-label={t("nav.language")}
      title={t("nav.language")}
      className={`h-9 px-3 rounded-full bg-muted/60 flex items-center justify-center text-xs font-bold tracking-wide text-foreground hover:bg-muted transition-colors ${className}`}
    >
      {lang.toUpperCase()}
    </button>
  );
};

export default LanguageToggle;
