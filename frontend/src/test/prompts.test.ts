import { describe, expect, it } from "vitest";
import { translations, type TranslationKey } from "@/i18n/translations";
import type { ApiListing } from "@/lib/api";
import {
  describeLikedPrompt,
  interleave,
  isLikablePrompt,
  listingPrompts,
  personPrompts,
  roommatePrompts,
  type PromptContext,
} from "@/lib/prompts";

// Gerçek sözlükle çalışır: kartın cümlesi ekranda göründüğü gibi sınanır.
const ctx = (lang: "tr" | "en"): PromptContext => {
  const locale = lang === "tr" ? "tr-TR" : "en-US";
  const fmt = new Intl.NumberFormat(locale);
  return {
    locale,
    n: v => fmt.format(v),
    t: (key: TranslationKey, vars?: Record<string, string | number>) =>
      translations[lang][key].replace(/\{(\w+)\}/g, (_, k) => String(vars?.[k] ?? "")),
  };
};
const tr = ctx("tr");
const en = ctx("en");

const listing = (over: Partial<ApiListing> = {}): ApiListing => ({
  id: 7,
  type: "ev_ilani",
  title: "Moda'da oda",
  description: "Güneşli, sessiz bir oda.",
  district: "Kadıköy",
  neighborhood: null,
  photos: ["a.jpg", "b.jpg", "c.jpg"],
  rent: 12000,
  room_count: "2+1",
  is_active: true,
  created_at: "2026-10-01T10:00:00",
  owner_id: 3,
  owner_name: "Ayşe",
  owner_university: "Boğaziçi Üniversitesi",
  owner_profile: null,
  ...over,
});

describe("roommatePrompts", () => {
  it("boş alan için kart üretmez", () => {
    expect(roommatePrompts({}, tr)).toEqual([]);
  });

  it("uyku, alışkanlık ve bölümü kişinin ağzından yazar", () => {
    const prompts = roommatePrompts(
      { sleep_schedule: "gece", smoking: false, alcohol: true, pets: false, department: "Mimarlık", year: 3 },
      tr,
    );
    expect(prompts.map(p => [p.key, p.question, p.answer])).toEqual([
      ["sleep", "Uyku düzenim", "Gece kuşuyum"],
      ["habits", "Ev hayatında ben", "Sigara içmem, alkol kullanırım, evde hayvan istemem."],
      ["studies", "Okuduğum bölüm", "Mimarlık, 3. sınıf"],
    ]);
  });

  it("bilinmeyen alışkanlığı varsayılanla doldurmaz", () => {
    // Eskiden null "içmez" sayılıyordu; kart kişinin ağzından konuştuğu için
    // söylemediği bir şeyi ona söyletmemeli.
    const [habits] = roommatePrompts({ alcohol: false }, tr);
    expect(habits.answer).toBe("Alkol kullanmam.");
  });

  it("cümlenin ilk harfini dilin kuralıyla büyütür", () => {
    const [habits] = roommatePrompts({ pets: true }, en);
    expect(habits.answer).toBe("I love pets.");
  });

  it("tanınmayan uyku değerini atlar", () => {
    expect(roommatePrompts({ sleep_schedule: "?" }, tr)).toEqual([]);
  });
});

describe("personPrompts", () => {
  it("bütçeyi fosforlu kalemle, semtleri sırasıyla ekler", () => {
    const prompts = personPrompts(
      { budget_min: 8000, budget_max: 12000, preferred_districts: ["Kadıköy", "Beşiktaş"] },
      tr,
    );
    expect(prompts).toEqual([
      { key: "budget", question: "Kiraya ayırabileceğim", answer: "8.000–12.000 TL/ay", marker: true },
      { key: "districts", question: "Oturmak istediğim semtler", answer: "Kadıköy, Beşiktaş" },
    ]);
  });
});

describe("listingPrompts", () => {
  it("ev kartları önce, sonra ilan sahibinin kartları", () => {
    const prompts = listingPrompts(
      listing({
        smoking_allowed: false,
        pets_allowed: true,
        furnished: true,
        internet_included: true,
        elevator: false,
        owner_profile: {
          department: null,
          year: null,
          sleep_schedule: "erken",
          smoking: null,
          pets: null,
          alcohol: null,
          photo: null,
        },
      }),
      tr,
    );
    expect(prompts.map(p => [p.key, p.answer])).toEqual([
      ["house_rules", "Sigara içilmez, evcil hayvan olur."],
      // Yalnızca açıkça "var" denenler; küçük harf Türkçe kuralıyla.
      ["amenities", "Eşyalı, internet dahil."],
      ["sleep", "Erken kalkarım"],
    ]);
  });

  it("kişisel ilanda ev kartı yok", () => {
    expect(listingPrompts(listing({ type: "kisisel_ilan", smoking_allowed: false }), tr)).toEqual([]);
  });

  it("destede üretilen her kart beğenilebilir", () => {
    const prompts = listingPrompts(
      listing({
        smoking_allowed: true,
        balcony: true,
        owner_profile: {
          department: "Fizik",
          year: 2,
          sleep_schedule: "esnek",
          smoking: true,
          pets: null,
          alcohol: null,
          photo: null,
        },
      }),
      tr,
    );
    expect(prompts).toHaveLength(5);
    expect(prompts.every(p => isLikablePrompt(p.key))).toBe(true);
  });
});

describe("isLikablePrompt", () => {
  it("bütçe ve semt kartı beğeni hedefi değildir", () => {
    expect(isLikablePrompt("budget")).toBe(false);
    expect(isLikablePrompt("districts")).toBe(false);
    expect(isLikablePrompt("description")).toBe(true);
  });
});

describe("interleave", () => {
  const prompts = personPrompts({ sleep_schedule: "gece", department: "Tıp", budget_min: 1, budget_max: 2 }, tr);

  it("kartla başlar, sırayla dizer, kalanı arkaya ekler", () => {
    const items = interleave(["b.jpg"], prompts, 1);
    expect(items.map(i => (i.kind === "photo" ? `photo:${i.index}` : i.prompt.key))).toEqual([
      "sleep",
      "photo:1",
      "studies",
      "budget",
    ]);
  });

  it("fazla fotoğrafı asıl sırasıyla ekler", () => {
    const items = interleave(["b.jpg", "c.jpg", "d.jpg"], prompts.slice(0, 1), 1);
    expect(items.map(i => (i.kind === "photo" ? `photo:${i.index}` : i.prompt.key))).toEqual([
      "sleep",
      "photo:1",
      "photo:2",
      "photo:3",
    ]);
  });

  it("ikisi de boşsa boş", () => {
    expect(interleave([], [])).toEqual([]);
  });
});

describe("describeLikedPrompt", () => {
  const me = { sleep_schedule: "gece", smoking: false };

  it("kartı alanın bugünkü verisinden üretir", () => {
    expect(describeLikedPrompt("sleep", me, undefined, tr)).toEqual({
      question: "Uyku düzenim",
      answer: "Gece kuşuyum",
    });
  });

  it("ilan yazısını ilandan okur", () => {
    expect(describeLikedPrompt("description", me, listing(), tr)).toEqual({
      question: "İlan yazısı",
      answer: "Güneşli, sessiz bir oda.",
    });
  });

  it("kart artık yoksa yalnızca soruyu verir", () => {
    // İlan kapandı ya da alan boşaltıldı: neyin beğenildiği yine söylenir.
    expect(describeLikedPrompt("amenities", me, undefined, tr)).toEqual({
      question: "Evde neler var",
      answer: null,
    });
  });

  it("bilinmeyen anahtarda hiçbir şey göstermez", () => {
    expect(describeLikedPrompt("maas", me, undefined, tr)).toBeNull();
  });
});
