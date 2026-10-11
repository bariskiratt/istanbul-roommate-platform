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

import SiteBar from "@/components/layout/SiteBar";
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
  const { t } = useI18n();

  return (
    <div className="min-h-screen bg-background">
      <SiteBar showBack />

      <main className="max-w-[44rem] mx-auto px-5 py-12">
        <h1 className="text-[2.5rem] leading-tight text-foreground">{t("privacy.title")}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{t("privacy.updated")}</p>
        <p className="mt-6 text-[17px] text-foreground leading-[1.7]">{t("privacy.intro")}</p>

        {SECTIONS.map(section => (
          <section key={section.heading} className="mt-10">
            <h2 className="text-2xl text-foreground">
              {t(section.heading)}
            </h2>
            {section.body.map(key => (
              <p key={key} className="mt-3 text-[16px] text-foreground leading-[1.7]">
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
