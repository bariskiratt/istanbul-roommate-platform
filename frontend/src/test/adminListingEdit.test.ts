import { describe, expect, it } from "vitest";
import {
  buildListingPatch,
  formFromListing,
  validateListingForm,
  type ListingEditForm,
} from "@/pages/Listings";
import type { AdminListing } from "@/lib/api";

/** Sunucunun döndürdüğü bir ev ilanı satırı (GET /api/admin/listings). */
const house = (over: Partial<AdminListing> = {}): AdminListing => ({
  id: 1,
  type: "ev_ilani",
  title: "Kadıköy'de oda",
  description: "Ferah, aydınlık.",
  district: "Kadıköy",
  neighborhood: "Caferağa Mah.",
  photos: ["a.jpg", "b.jpg", "c.jpg"],
  rent: 9000,
  room_count: "2+1",
  smoking_allowed: false,
  pets_allowed: true,
  // Üç değerli alanlar: true / false / null ("bilinmiyor").
  furnished: true,
  elevator: false,
  parking: null,
  internet_included: null,
  heating_included: null,
  balcony: null,
  natural_gas: null,
  budget_min: null,
  budget_max: null,
  is_active: true,
  created_at: "2026-07-01T10:00:00",
  owner_id: 7,
  owner_name: "Ayşe",
  owner_university: null,
  moderation_removed: false,
  active_before_removal: null,
  is_flagged: false,
  flag_reasons: [],
  flag_reasons_text: null,
  owner_suspended: false,
  reviewed_by: null,
  reviewed_at: null,
  review_note: null,
  ...over,
});

const personal = (over: Partial<AdminListing> = {}): AdminListing =>
  house({
    type: "kisisel_ilan",
    neighborhood: null,
    rent: null,
    room_count: null,
    budget_min: 4000,
    budget_max: 8000,
    ...over,
  });

const edit = (l: AdminListing, over: Partial<ListingEditForm> = {}): ListingEditForm => ({
  ...formFromListing(l),
  ...over,
});

describe("buildListingPatch", () => {
  it("hiçbir şey değişmediyse boş gövde üretir", () => {
    const l = house();
    expect(buildListingPatch(l, edit(l))).toEqual({});
  });

  it("yalnızca değişen alanları gönderir", () => {
    const l = house();
    const patch = buildListingPatch(l, edit(l, { title: "Yeni başlık", rent: "9500" }));
    expect(patch).toEqual({ title: "Yeni başlık", rent: 9500 });
  });

  it("metin alanlarını kırpar ve kırpılmış hâli değişmemişse göndermez", () => {
    const l = house();
    expect(buildListingPatch(l, edit(l, { title: "  Kadıköy'de oda  " }))).toEqual({});
    expect(buildListingPatch(l, edit(l, { description: "  Yeni metin  " }))).toEqual({
      description: "Yeni metin",
    });
  });

  it("dokunulmayan 'bilinmiyor' özelliği false'a çevirmez", () => {
    // En kritik kural: sunucu gönderilen her alanı yazar. Tüm kutuları toptan
    // yollamak, sahibinin hiç belirtmediği özellikleri "yok" yapardı.
    const l = house();
    expect(buildListingPatch(l, edit(l))).not.toHaveProperty("parking");
    expect(buildListingPatch(l, edit(l))).not.toHaveProperty("balcony");
  });

  it("işaretlenen 'bilinmiyor' özelliği true olarak gönderir", () => {
    const l = house();
    const form = edit(l);
    const patch = buildListingPatch(l, {
      ...form,
      features: { ...form.features, parking: true },
    });
    expect(patch).toEqual({ parking: true });
  });

  it("işareti kaldırılan özelliği false olarak gönderir", () => {
    const l = house();
    const form = edit(l);
    const patch = buildListingPatch(l, {
      ...form,
      features: { ...form.features, furnished: false },
    });
    expect(patch).toEqual({ furnished: false });
  });

  it("ilçe değişince mahalle seçimi de gönderilir", () => {
    const l = house();
    const patch = buildListingPatch(l, edit(l, { location: { district: "Şişli", neighborhood: "" } }));
    expect(patch).toEqual({ district: "Şişli", neighborhood: "" });
  });

  it("kişisel ilanda ev alanlarına hiç dokunmaz", () => {
    const l = personal();
    const form = edit(l);
    const patch = buildListingPatch(l, {
      ...form,
      // Form durumu tipler arasında korunsa bile bu alanlar gönderilmemeli.
      rent: "9000",
      roomCount: "3+1",
      features: { ...form.features, parking: true },
      budgetMax: "9000",
    });
    expect(patch).toEqual({ budget_max: 9000 });
  });

  it("boş bırakılan sayı alanı 'dokunma' demektir", () => {
    const l = house();
    expect(buildListingPatch(l, edit(l, { rent: "" }))).toEqual({});
  });
});

describe("validateListingForm", () => {
  it("geçerli formda hata yok", () => {
    const l = house();
    expect(validateListingForm(l, edit(l))).toBeNull();
  });

  it("kısa başlığı yakalar", () => {
    const l = house();
    expect(validateListingForm(l, edit(l, { title: "ab" }))).toBe("listings.errTitle");
  });

  it("boş açıklamayı yakalar", () => {
    const l = house();
    expect(validateListingForm(l, edit(l, { description: "   " }))).toBe("listings.errDescription");
  });

  it("ilçesiz kaydı yakalar", () => {
    const l = house();
    const form = edit(l, { location: { district: "", neighborhood: "" } });
    expect(validateListingForm(l, form)).toBe("listings.errDistrict");
  });

  it("sıfır ya da negatif kirayı yakalar", () => {
    const l = house();
    expect(validateListingForm(l, edit(l, { rent: "0" }))).toBe("listings.errRent");
    expect(validateListingForm(l, edit(l, { rent: "-5" }))).toBe("listings.errRent");
  });

  it("bütçe sınırlarını ETKİN değerlerle karşılaştırır", () => {
    // Alt sınır boş bırakıldı: kayıttaki 4000 geçerli kalır, 3000 ile çelişmez.
    const l = personal();
    expect(validateListingForm(l, edit(l, { budgetMin: "", budgetMax: "3000" }))).toBe(
      "listings.errBudget",
    );
    expect(validateListingForm(l, edit(l, { budgetMin: "", budgetMax: "9000" }))).toBeNull();
    expect(validateListingForm(l, edit(l, { budgetMin: "9000" }))).toBe("listings.errBudget");
  });

  it("bütçede sayı olmayan değeri yakalar", () => {
    const l = personal();
    expect(validateListingForm(l, edit(l, { budgetMin: "abc" }))).toBe("listings.errBudgetValue");
  });
});
