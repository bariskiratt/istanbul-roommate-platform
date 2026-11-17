/**
 * İLAN ONAYI: ONAYLA / REDDET DOĞRU CÜMLEYLE ANLATILMALI.
 *
 * Onay bekleyen ilanın "Onayla" düğmesi sunucuda "clear" ucunu çağırır,
 * ama yöneticiye "İşaret kaldırıldı" demek yanlış olurdu: ilan yayına girdi.
 * "Reddet" de "remove" değildir: ilan sahibine sebebiyle geri döner ve
 * yanıtı is_active:false taşısa da bu bir uyarı değil, istenen sonuçtur.
 */

import { describe, expect, it } from "vitest";

import { restoreOutcome } from "@/pages/Admin";
import { translations } from "@/i18n/translations";

describe("ilan onayı sonuç cümleleri", () => {
  it("onay 'işaret kaldırıldı' değil 'yayında' der", () => {
    const { key, tone } = restoreOutcome("approveListing", { is_active: true });
    expect(key).toBe("admin.doneApprove");
    expect(tone).toBe("success");
    expect(key).not.toBe("admin.doneClear");
  });

  it("ret, kapalı kalan ilana rağmen uyarıya kaymaz", () => {
    expect(restoreOutcome("rejectListing", { is_active: false })).toEqual({
      key: "admin.doneReject",
      tone: "success",
    });
  });

  it("yeni metinlerin iki dilde de karşılığı var", () => {
    const keys = [
      "admin.doneApprove",
      "admin.doneReject",
      "admin.actionReject",
      "admin.pendingReviewNote",
      "admin.dlgRejectReasonLabel",
      "profile.rejected",
      "profile.rejectedReason",
      "profile.resubmit",
    ] as const;
    for (const key of keys) {
      expect(translations.tr[key]).toBeTruthy();
      expect(translations.en[key]).toBeTruthy();
    }
    // Sahibine gösterilen sebep yer tutucusu iki dilde de duruyor.
    expect(translations.tr["profile.rejectedReason"]).toContain("{reason}");
    expect(translations.en["profile.rejectedReason"]).toContain("{reason}");
  });
});
