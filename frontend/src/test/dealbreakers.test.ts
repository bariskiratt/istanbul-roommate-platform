/**
 * İstemediklerim: eleme sunucuda (backend/tests/test_dealbreakers.py); burada
 * formun gönderdiği listenin her zaman sunucunun kabul ettiği biçimde
 * olduğu sınanıyor. Bilinmeyen bir anahtar PATCH /me'yi 422'ye düşürür ve
 * kayıt son adımda takılırdı.
 */

import { beforeEach, describe, expect, it } from "vitest";

import { DEALBREAKERS, normalizeDealbreakers, toggleDealbreaker } from "@/lib/dealbreakers";
import { loadOnboardingDraft } from "@/lib/onboardingDraft";
import { translations, type TranslationKey } from "@/i18n/translations";

describe("istemediklerim", () => {
  it("bilinmeyeni ve tekrarı atar, sırayı listeye göre kurar", () => {
    expect(normalizeDealbreakers(["early_bird", "gender", "smoking", "smoking"])).toEqual([
      "smoking",
      "early_bird",
    ]);
    expect(normalizeDealbreakers(undefined)).toEqual([]);
    expect(normalizeDealbreakers(null)).toEqual([]);
  });

  it("seçim açılıp kapanır", () => {
    const on = toggleDealbreaker([], "pets");
    expect(on).toEqual(["pets"]);
    expect(toggleDealbreaker(on, "pets")).toEqual([]);
    expect(toggleDealbreaker(["night_owl"], "smoking")).toEqual(["smoking", "night_owl"]);
  });

  it("sunucunun kapalı listesiyle aynı anahtarlar", () => {
    // backend/app/dealbreakers.py Dealbreaker ile aynı olmalı.
    expect([...DEALBREAKERS]).toEqual(["smoking", "alcohol", "pets", "night_owl", "early_bird"]);
  });

  it("her seçeneğin iki dilde etiketi var", () => {
    const keys: TranslationKey[] = [
      "deal.smoking",
      "deal.alcohol",
      "deal.pets",
      "deal.nightOwl",
      "deal.earlyBird",
      "deal.mutual",
      "ob.stepDealTitle",
      "ob.stepDealSub",
    ];
    for (const key of keys) {
      expect(translations.tr[key], key).toBeTruthy();
      expect(translations.en[key], key).toBeTruthy();
    }
  });
});

describe("kayıt taslağındaki istemediklerim", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("eski ya da bozuk taslaktaki bilinmeyen anahtar atılır", () => {
    window.sessionStorage.setItem(
      "onboarding-draft",
      JSON.stringify({ name: "Ayşe", dealbreakers: ["smoking", "eski_anahtar", 3] }),
    );
    const draft = loadOnboardingDraft();
    expect(draft.name).toBe("Ayşe");
    expect(draft.dealbreakers).toEqual(["smoking"]);
  });

  it("taslağı olmayan eski kayıt boş listeyle açılır", () => {
    window.sessionStorage.setItem("onboarding-draft", JSON.stringify({ name: "Ayşe" }));
    expect(loadOnboardingDraft().dealbreakers).toEqual([]);
  });
});
