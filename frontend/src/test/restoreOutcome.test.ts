/**
 * GERİ ALMA SONUCU DOĞRU CÜMLEYLE ANLATILMALI.
 *
 * Sunucunun /api/admin/{kind}/{id}/restore ucu 200 dönse bile kaydı HİÇ
 * DEĞİŞTİRMEMİŞ olabilir. Üç ayrı sonuç vardır ve üçü aynı cümleyle
 * anlatılamaz:
 *
 *   1. restored:false  -> mesajın özgün metni hiç saklanmamış (bu sütunlar
 *      eklenmeden önce kaldırılmış eski kayıt). Sunucu kayda BİLEREK
 *      dokunmaz: moderation_removed True kalır ve satır "Kaldırılanlar"
 *      kuyruğunda bulunabilir olmayı sürdürür.
 *   2. content_restored:false -> kayıt geri alındı (kuyruktan düştü) ama
 *      saklanan metin çözülemiyor (anahtar kaybolmuş/dönmüş).
 *   3. is_active:false (ilan) -> kaldırma geri alındı ama ilan yayına
 *      girmedi, çünkü sahibi onu zaten kendi kapatmıştı.
 *
 * Bu dosya neden var: 1. durum arayüzde 2. durumla AYNI cümleyi basıyordu
 * ("Kayıt geri alındı ama..."), üstelik api.ts'te `restored` alanı `true`
 * SABİTİ olarak yazıldığı için TypeScript `false` ihtimalini eleyip hatayı
 * görünmez kılıyordu. Sonuç: hiçbir şeyin değişmediği bir istekten sonra
 * yöneticiye "geri alındı" deniyordu.
 */

import { describe, expect, it } from "vitest";

import { restoreOutcome } from "@/pages/Admin";
import { translations } from "@/i18n/translations";
import type { RestoreResult } from "@/lib/api";

/** Sunucunun gerçek yanıtlarından türetilmiş gövdeler (canlı çıktıyla birebir). */
const METNI_HIC_SAKLANMAMIS: Partial<RestoreResult> = {
  kind: "message",
  restored: false,
  is_active: null,
  moderation_removed: true,
  content_recoverable: false,
  content_restored: false,
};

const METIN_COZULEMIYOR: Partial<RestoreResult> = {
  kind: "message",
  restored: true,
  is_active: null,
  moderation_removed: false,
  content_recoverable: true,
  content_restored: false,
};

const METIN_GERI_KONDU: Partial<RestoreResult> = {
  kind: "message",
  restored: true,
  is_active: null,
  moderation_removed: false,
  content_recoverable: true,
  content_restored: true,
};

const ILAN_KAPALI_KALDI: Partial<RestoreResult> = {
  kind: "listing",
  restored: true,
  is_active: false,
  moderation_removed: false,
  content_recoverable: null,
  content_restored: null,
};

const ILAN_YAYINA_DONDU: Partial<RestoreResult> = {
  kind: "listing",
  restored: true,
  is_active: true,
  moderation_removed: false,
  content_recoverable: null,
  content_restored: null,
};

describe("restoreOutcome", () => {
  it("kayda hiç dokunulmadıysa 'geri alındı' DEMEZ", () => {
    const { key, tone } = restoreOutcome("restoreMessage", METNI_HIC_SAKLANMAMIS);
    expect(key).toBe("admin.doneRestoreMessageUnrecoverable");
    expect(tone).toBe("warning");
    // Kritik: bu, "kayıt geri alındı ama metin gelmedi" cümlesi OLMAMALI.
    expect(key).not.toBe("admin.doneRestoreMessageNoText");
    expect(key).not.toBe("admin.doneRestoreMessage");
  });

  it("kayıt geri alındı ama metin çözülemiyorsa 'metin geri kondu' DEMEZ", () => {
    const { key, tone } = restoreOutcome("restoreMessage", METIN_COZULEMIYOR);
    expect(key).toBe("admin.doneRestoreMessageNoText");
    expect(tone).toBe("warning");
    expect(key).not.toBe("admin.doneRestoreMessage");
  });

  it("metin gerçekten okunabilir döndüyse başarı cümlesini basar", () => {
    expect(restoreOutcome("restoreMessage", METIN_GERI_KONDU)).toEqual({
      key: "admin.doneRestoreMessage",
      tone: "success",
    });
  });

  it("ilan yayına girmediyse 'yeniden yayında' DEMEZ", () => {
    const { key, tone } = restoreOutcome("restoreListing", ILAN_KAPALI_KALDI);
    expect(key).toBe("admin.doneRestoreListingStillClosed");
    expect(tone).toBe("warning");
    expect(key).not.toBe("admin.doneRestoreListing");
  });

  it("ilan gerçekten yayına döndüyse başarı cümlesini basar", () => {
    expect(restoreOutcome("restoreListing", ILAN_YAYINA_DONDU)).toEqual({
      key: "admin.doneRestoreListing",
      tone: "success",
    });
  });

  it("geri alma DIŞINDAKİ eylemler kendi cümlelerini korur", () => {
    // reviewFlagged("remove") yanıtı da is_active:false taşır; bu bir uyarı
    // değil, istenen sonuçtur — geri alma uyarısına kaymamalı.
    expect(restoreOutcome("removeListing", { is_active: false })).toEqual({
      key: "admin.doneRemoveListing",
      tone: "success",
    });
    expect(restoreOutcome("clear", {})).toEqual({
      key: "admin.doneClear",
      tone: "success",
    });
    expect(restoreOutcome("suspend", {})).toEqual({
      key: "admin.doneSuspend",
      tone: "success",
    });
  });

  it("ürettiği HER anahtar iki sözlükte de gerçekten tanımlı", () => {
    const bodies: Array<[Parameters<typeof restoreOutcome>[0], Partial<RestoreResult>]> = [
      ["restoreMessage", METNI_HIC_SAKLANMAMIS],
      ["restoreMessage", METIN_COZULEMIYOR],
      ["restoreMessage", METIN_GERI_KONDU],
      ["restoreListing", ILAN_KAPALI_KALDI],
      ["restoreListing", ILAN_YAYINA_DONDU],
    ];
    for (const [kind, body] of bodies) {
      const { key } = restoreOutcome(kind, body);
      expect(translations.tr[key], `tr: ${key}`).toBeTruthy();
      expect(translations.en[key], `en: ${key}`).toBeTruthy();
    }
  });

  it("uyarı cümleleri 'geri alındı/yayında' iddiasını taşımaz", () => {
    // Metin hiç saklanmamış durumunda basılan cümle, olmamış bir şeyi
    // olmuş gibi anlatmamalı.
    const tr = translations.tr["admin.doneRestoreMessageUnrecoverable"];
    const en = translations.en["admin.doneRestoreMessageUnrecoverable"];
    expect(tr).toContain("Kayıt değişmedi");
    expect(tr).toContain("kaldırılmış kalıyor");
    expect(en.toLowerCase()).toContain("nothing changed");
    expect(en.toLowerCase()).toContain("stays removed");
  });
});
