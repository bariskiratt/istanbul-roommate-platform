/**
 * Gizlilik ve KVKK aydınlatma metni.
 *
 * Metnin tamamı translations.ts içindeki "privacy.*" anahtarlarında; buradaki
 * iş yalnızca düzen. Her cümle kodun GERÇEKTE yaptığını anlatır — davranış
 * değişirse metin de değişmeli.
 *
 * Ayarlar'daki "Gizlilik" düğmesi bir dönem /safety'ye gidiyordu: kullanıcı
 * gizlilik politikası bekleyip güvenlik ipuçları buluyordu. O bağlantı artık
 * buraya geliyor.
 */

import { ArrowLeft, Home } from "lucide-react";
import { useNavigate } from "react-router-dom";

import LanguageToggle from "@/components/LanguageToggle";
import ThemeToggle from "@/components/ThemeToggle";
import { useI18n } from "@/i18n";
import type { TranslationKey } from "@/i18n/translations";
import { BRAND } from "@/lib/brand";

/** Bir bölüm: başlık + bir veya birden çok paragraf. */
const SECTIONS: { heading: TranslationKey; body: TranslationKey[] }[] = [
  { heading: "privacy.controllerTitle", body: ["privacy.controllerBody"] },
  {
    heading: "privacy.dataTitle",
    body: [
      "privacy.dataAccount",
      "privacy.dataProfile",
      "privacy.dataListing",
      "privacy.dataActivity",
      "privacy.dataTechnical",
      "privacy.dataNoTracking",
    ],
  },
  { heading: "privacy.purposeTitle", body: ["privacy.purposeBody"] },
  {
    heading: "privacy.shareTitle",
    body: [
      "privacy.shareBody",
      "privacy.shareRender",
      "privacy.shareNeon",
      "privacy.shareCloudflare",
      "privacy.shareVercel",
      "privacy.shareBrevo",
      "privacy.shareNoAi",
      "privacy.shareNoSale",
    ],
  },
  {
    heading: "privacy.securityTitle",
    body: ["privacy.securityBody", "privacy.securityNotE2e"],
  },
  {
    heading: "privacy.retentionTitle",
    body: ["privacy.retentionBody", "privacy.retentionAudit"],
  },
  {
    heading: "privacy.rightsTitle",
    body: ["privacy.rightsBody", "privacy.rightsHow"],
  },
  { heading: "privacy.changesTitle", body: ["privacy.changesBody"] },
];

export default function Privacy() {
  const navigate = useNavigate();
  const { t } = useI18n();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-40 bg-background/90 backdrop-blur-lg border-b border-border">
        <div className="max-w-3xl mx-auto px-6 h-16 flex items-center justify-between gap-3">
          <button
            onClick={() => navigate(-1)}
            aria-label={t("common.back")}
            className="w-10 h-10 -ml-2 rounded-full flex items-center justify-center text-foreground hover:bg-muted transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <button
            onClick={() => navigate("/")}
            className="flex items-center gap-2 flex-1"
          >
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Home className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-extrabold text-lg text-foreground tracking-tight">
              {BRAND}
            </span>
          </button>
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <h1 className="text-3xl font-bold text-foreground">{t("privacy.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("privacy.updated")}</p>
        <p className="mt-6 text-foreground leading-relaxed">{t("privacy.intro")}</p>

        {SECTIONS.map(section => (
          <section key={section.heading} className="mt-10">
            <h2 className="text-xl font-semibold text-foreground">
              {t(section.heading)}
            </h2>
            {section.body.map(key => (
              <p key={key} className="mt-3 text-foreground leading-relaxed">
                {t(key)}
              </p>
            ))}
          </section>
        ))}

        <footer className="mt-14 pt-6 border-t border-border">
          <p className="text-xs text-muted-foreground">© 2026 {BRAND}</p>
        </footer>
      </main>
    </div>
  );
}
