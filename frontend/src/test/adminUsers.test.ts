/**
 * KULLANICI YÖNETİMİ + DENETİM KAYDI.
 *
 * Bu dosyanın koruduğu iki söz var:
 *
 * 1. YÖNETİCİ SATIRINDA YIKICI DÜĞME OLMAZ. Sunucu yöneticinin kendisini
 *    (400) ve başka bir yöneticiyi (403) askıya almayı/silmeyi reddediyor.
 *    Düğmeyi gösterip kullanıcıya hata aldırmak, olmayan bir yetkiyi varmış
 *    gibi göstermektir. Kısıt bir yetki meselesi değil emniyet kilidi: son
 *    yönetici kendini kilitlerse platformun yönetimi geri gelmez.
 *
 * 2. DENETİM KAYDI BOZUK BİR `detail` YÜZÜNDEN KAYBOLMAZ. `detail` alanı JSON
 *    METNİDİR (nesne değil) ve kaydın asıl bilgisi — kim, ne zaman, neyi,
 *    hangi gerekçeyle — kendi sütunlarında durur. Ayrıştırma hatası tüm satırı
 *    gizleseydi, "geçen hafta neyi neden sildim" sorusunun cevabı tam da
 *    cevaplanması gereken kayıtta yok olurdu.
 */

import { describe, expect, it } from "vitest";

import { parseActionDetail, restoreOutcome, userRowActions } from "@/pages/Admin";
import { translations, type TranslationKey } from "@/i18n/translations";
import type { AdminUserRow } from "@/lib/api";

const user = (over: Partial<AdminUserRow> = {}): AdminUserRow => ({
  id: 4,
  email: null,
  name: "Ayşe",
  university: "İTÜ",
  is_admin: false,
  is_suspended: false,
  suspended_at: null,
  suspended_reason: null,
  suspended_by: null,
  unsuspended_at: null,
  unsuspended_by: null,
  last_suspension_reason: null,
  created_at: "2026-05-01T09:00:00",
  ...over,
});

describe("userRowActions", () => {
  it("normal hesapta askıya alma ve silme sunar", () => {
    expect(userRowActions(user())).toEqual(["suspend", "deleteUser"]);
  });

  it("askıdaki hesapta askıyı kaldırmayı sunar, ikinci kez askıya almayı değil", () => {
    const actions = userRowActions(user({ is_suspended: true }));
    expect(actions).toEqual(["unsuspend", "deleteUser"]);
    expect(actions).not.toContain("suspend");
  });

  it("YÖNETİCİ satırında hiçbir yıkıcı eylem göstermez", () => {
    expect(userRowActions(user({ is_admin: true }))).toEqual([]);
    // Askıya alınmış bir hesap sonradan yönetici yapılmış olabilir; koruma
    // yine de geçerlidir, yoksa 403 alan bir "Askıyı kaldır" düğmesi kalırdı.
    expect(userRowActions(user({ is_admin: true, is_suspended: true }))).toEqual([]);
  });
});

describe("parseActionDetail", () => {
  it("nesne JSON'unu ayrıştırır", () => {
    const raw = JSON.stringify({ title: "Kadıköy'de oda", owner_id: 7 });
    expect(parseActionDetail(raw)).toEqual({ title: "Kadıköy'de oda", owner_id: 7 });
  });

  it("detail yokken null döner (yayına alma kaydında detail yazılmıyor)", () => {
    expect(parseActionDetail(null)).toBeNull();
    expect(parseActionDetail("")).toBeNull();
  });

  it("bozuk JSON'da FIRLATMAZ; satırın geri kalanı okunabilir kalsın", () => {
    expect(parseActionDetail("{bozuk")).toBeNull();
  });

  it("dizi ve skaler değerleri nesne saymaz", () => {
    // Object.entries bir dizide sayı anahtarları üretir; "0: a" diye bir alan
    // gösterip kaydı anlamsızlaştırmaktansa hiç göstermemek doğru.
    expect(parseActionDetail("[1,2]")).toBeNull();
    expect(parseActionDetail('"metin"')).toBeNull();
    expect(parseActionDetail("null")).toBeNull();
  });

  it("düzenleme kaydında önceki metni korur (tek kalan kopya)", () => {
    const raw = JSON.stringify({
      fields: ["description", "title"],
      before: { title: "Eski başlık", description: "Eski açıklama" },
    });
    const parsed = parseActionDetail(raw);
    expect(parsed?.before).toEqual({ title: "Eski başlık", description: "Eski açıklama" });
  });
});

describe("restoreOutcome — hesap silme", () => {
  it("silme yanıtını geri alma sanıp uyarı basmaz", () => {
    // Sunucu yanıtı {kind,id,deleted,action_id,cleanup} — `restored` ya da
    // `content_restored` yok. Geri alma dallarının hiçbiri tetiklenmemeli.
    const { key, tone } = restoreOutcome("deleteUser", {});
    expect(key).toBe("admin.doneDeleteUser");
    expect(tone).toBe("success");
  });
});

describe("i18n", () => {
  /** Arayüzün bu görevde kullandığı, iki sözlükte de bulunması gereken anahtarlar. */
  const keys: TranslationKey[] = [
    "admin.tabUsers",
    "admin.tabActions",
    "admin.userSearchLabel",
    "admin.userSearchPlaceholder",
    "admin.userSearchClear",
    "admin.userStatusActive",
    "admin.badgeNormal",
    "admin.emailOnlySuspended",
    "admin.userCreatedAt",
    "admin.userUnsuspendedAt",
    "admin.lastSuspensionReason",
    "admin.actionDeleteUser",
    "admin.adminProtectedNote",
    "admin.resultCount",
    "admin.emptyUsers",
    "admin.emptyUsersDesc",
    "admin.emptyUsersFilteredDesc",
    "admin.dlgDeleteUserTitle",
    "admin.dlgDeleteUserDesc",
    "admin.dlgDeleteUserWarn",
    "admin.dlgDeleteUserReasonLabel",
    "admin.dlgDeleteUserReasonPlaceholder",
    "admin.doneDeleteUser",
    "admin.doneDeleteUserDesc",
    "admin.logIntro",
    "admin.logListingDelete",
    "admin.logUserDelete",
    "admin.logListingUpdate",
    "admin.logListingPublish",
    "admin.logActorLabel",
    "admin.logActorDeleted",
    "admin.logReason",
    "admin.logDetail",
    "admin.logRawNote",
    "admin.logValueTrue",
    "admin.logValueFalse",
    "admin.logBefore",
    "admin.logBeforeNote",
    "admin.emptyActionsTitle",
    "admin.emptyActionsDesc",
    "admin.emptyActionsFilteredDesc",
  ];

  it("her anahtar iki sözlükte de dolu", () => {
    for (const key of keys) {
      expect(translations.tr[key], `tr: ${key}`).toBeTruthy();
      expect(translations.en[key], `en: ${key}`).toBeTruthy();
    }
  });

  it("yer tutucular iki dilde birebir aynı", () => {
    // Eksik bir yer tutucu sessizce "{date}" basar; fazlası hiç dolmaz.
    const slots = (v: string) => [...v.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort();
    for (const key of keys) {
      expect(slots(translations.en[key]), `slot: ${key}`).toEqual(slots(translations.tr[key]));
    }
  });

  it("iki sözlük birebir aynı anahtar kümesine sahip", () => {
    expect(Object.keys(translations.en).sort()).toEqual(Object.keys(translations.tr).sort());
  });

  it("silme metni geri alınamazlığı ve kaybolan sohbetleri saklamaz", () => {
    // Karşı taraftaki kişiler de o sohbetleri kaybediyor (purge_user
    // eşleşmeleri siliyor); onay penceresi bunu söylemek zorunda.
    expect(translations.tr["admin.dlgDeleteUserDesc"]).toContain("sohbet");
    expect(translations.en["admin.dlgDeleteUserDesc"]).toContain("chats");
    expect(translations.tr["admin.dlgDeleteUserWarn"]).toContain("geri alınamaz");
    expect(translations.en["admin.dlgDeleteUserWarn"]).toContain("cannot be undone");
  });
});
