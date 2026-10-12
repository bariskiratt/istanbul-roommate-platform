/**
 * KAYIT FORMU YENİLEMEYE DAYANMALI.
 *
 * Eskiden kayıt sırasında sayfayı yenilemek formu sıfırlıyordu: kod adımındaki
 * kişi baştan başlıyor, profil adımlarındaki kişi girdiği her şeyi
 * kaybediyordu. Taslak sessionStorage'da tutulur; bu dosya taslağın geri
 * okunmasını ve bozuk ya da eski bir taslağın formu çökertmemesini sınar.
 */

import { beforeEach, describe, expect, it } from "vitest";

import {
  EMPTY_ONBOARDING_DRAFT,
  clearOnboardingDraft,
  loadOnboardingDraft,
  profileIncomplete,
  saveOnboardingDraft,
} from "@/lib/onboardingDraft";

describe("onboarding taslağı", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("kaydedileni geri okur", () => {
    const draft = {
      ...EMPTY_ONBOARDING_DRAFT,
      step: 4,
      email: "ayse@itu.edu.tr",
      registeredEmail: "ayse@itu.edu.tr",
      name: "Ayşe",
      budget: [6000, 9000],
      district: ["Kadıköy"],
      photos: ["https://evdes.tr/uploads/a.jpg"],
    };
    saveOnboardingDraft(draft);
    expect(loadOnboardingDraft()).toEqual(draft);
  });

  it("taslak yoksa boş formla başlar", () => {
    expect(loadOnboardingDraft()).toEqual(EMPTY_ONBOARDING_DRAFT);
  });

  it("türü tutmayan alanı almaz, gerisini korur", () => {
    window.sessionStorage.setItem(
      "onboarding-draft",
      JSON.stringify({ step: "4", name: "Ayşe", photos: "a.jpg", budget: { min: 1 } }),
    );
    const draft = loadOnboardingDraft();
    expect(draft.name).toBe("Ayşe");
    expect(draft.step).toBe(0);
    expect(draft.photos).toEqual([]);
    expect(draft.budget).toEqual([4000, 8000]);
  });

  it("bozuk JSON formu çökertmez", () => {
    window.sessionStorage.setItem("onboarding-draft", "{bozuk");
    expect(loadOnboardingDraft()).toEqual(EMPTY_ONBOARDING_DRAFT);
  });

  it("temizlenince boşa döner", () => {
    saveOnboardingDraft({ ...EMPTY_ONBOARDING_DRAFT, name: "Ayşe" });
    clearOnboardingDraft();
    expect(loadOnboardingDraft().name).toBe("");
  });

  it("boş taslak paylaşılan varsayılanları değiştirmez", () => {
    const draft = loadOnboardingDraft();
    draft.district.push("Kadıköy");
    expect(EMPTY_ONBOARDING_DRAFT.district).toEqual([]);
  });
});

describe("profileIncomplete", () => {
  it("adı boş hesap kaydı bitirmemiştir", () => {
    expect(profileIncomplete({ name: "" })).toBe(true);
    expect(profileIncomplete({ name: "  " })).toBe(true);
  });

  it("adı olan hesap ve oturumsuz ziyaretçi yarım sayılmaz", () => {
    expect(profileIncomplete({ name: "Ayşe" })).toBe(false);
    expect(profileIncomplete(null)).toBe(false);
  });
});
