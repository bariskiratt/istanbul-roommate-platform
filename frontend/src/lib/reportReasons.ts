import type { TranslationKey } from "@/i18n/translations";

// Sunucudan gelen bildirim sebebi anahtarlarının arayüz etiketleri.
// Liste sunucuda kapalıdır (GET /api/reports/reasons); burada karşılığı olmayan
// bir anahtar gelirse çağıran ham değeri basar, yani yeni bir sebep
// eklendiğinde arayüz kırılmaz. Hem ReportDialog hem yönetim paneli bunu
// kullanır — etiketler iki yerde ayrışmasın.
const reasonKeys: Record<string, TranslationKey> = {
  spam: "report.reasonSpam",
  dolandiricilik: "report.reasonScam",
  taciz: "report.reasonHarassment",
  uygunsuz_icerik: "report.reasonInappropriate",
  sahte_ilan: "report.reasonFake",
  diger: "report.reasonOther",
};

/** Bilinen sebep için çeviri anahtarı, bilinmeyen için null. */
export const reportReasonKey = (reason: string): TranslationKey | null =>
  reasonKeys[reason] ?? null;
