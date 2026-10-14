import { describe, expect, it } from "vitest";
import type { ApiListing, OwnerProfile } from "@/lib/api";
import {
  defaultFilters,
  isDefaultFilters,
  listingPrice,
  matchesFilters,
  priceHistogram,
  type ListingFilters,
} from "@/lib/deckFilters";

const owner = (over: Partial<OwnerProfile> = {}): OwnerProfile => ({
  department: "Mimarlık",
  year: 3,
  sleep_schedule: "erken",
  smoking: false,
  pets: true,
  alcohol: false,
  photo: null,
  ...over,
});

const house = (over: Partial<ApiListing> = {}): ApiListing => ({
  id: 1,
  type: "ev_ilani",
  title: "Moda'da oda",
  description: "Güneşli oda",
  district: "Kadıköy",
  neighborhood: null,
  photos: ["a.jpg", "b.jpg", "c.jpg"],
  rent: 12000,
  room_count: "2+1",
  smoking_allowed: false,
  pets_allowed: true,
  is_active: true,
  created_at: "2026-10-01T10:00:00",
  owner_id: 3,
  owner_name: "Ayşe",
  owner_university: "Boğaziçi Üniversitesi",
  owner_profile: owner(),
  ...over,
});

const person = (over: Partial<ApiListing> = {}): ApiListing =>
  house({
    type: "kisisel_ilan",
    rent: undefined,
    room_count: undefined,
    smoking_allowed: undefined,
    pets_allowed: undefined,
    budget_min: 8000,
    budget_max: 12000,
    ...over,
  });

const withFilters = (over: Partial<ListingFilters>): ListingFilters => ({
  ...defaultFilters,
  ...over,
});

describe("matchesFilters: yaşam tarzı", () => {
  it("alkol ve uyku çipleri ilan sahibinin cevabına bakar (eskiden etkisizdi)", () => {
    const drinker = house({ owner_profile: owner({ alcohol: true, sleep_schedule: "gece" }) });
    expect(matchesFilters(drinker, withFilters({ lifestyle: ["noAlcohol"] }))).toBe(false);
    expect(matchesFilters(drinker, withFilters({ lifestyle: ["earlyBird"] }))).toBe(false);
    expect(matchesFilters(drinker, withFilters({ lifestyle: ["nightOwl"] }))).toBe(true);
    expect(matchesFilters(house(), withFilters({ lifestyle: ["noAlcohol", "earlyBird"] }))).toBe(true);
  });

  it("cevabı bilinmeyen kişi eşleşme sayılmaz", () => {
    const unknown = house({ owner_profile: owner({ alcohol: null, sleep_schedule: null }) });
    expect(matchesFilters(unknown, withFilters({ lifestyle: ["noAlcohol"] }))).toBe(false);
    expect(matchesFilters(unknown, withFilters({ lifestyle: ["earlyBird"] }))).toBe(false);
    // Profil hiç gelmediyse (girişsiz istek) de aynı.
    expect(matchesFilters(house({ owner_profile: null }), withFilters({ lifestyle: ["noAlcohol"] }))).toBe(false);
  });

  it("ev ilanında sigara ve hayvan evin kuralıdır", () => {
    // Sahibi sigara içse de evde içilmiyorsa ilan geçer.
    const strictHouse = house({ owner_profile: owner({ smoking: true, pets: false }) });
    expect(matchesFilters(strictHouse, withFilters({ lifestyle: ["noSmoke", "petFriendly"] }))).toBe(true);
    expect(matchesFilters(house({ smoking_allowed: true }), withFilters({ lifestyle: ["noSmoke"] }))).toBe(false);
    expect(matchesFilters(house({ smoking_allowed: undefined }), withFilters({ lifestyle: ["noSmoke"] }))).toBe(false);
    expect(matchesFilters(house({ pets_allowed: false }), withFilters({ lifestyle: ["petFriendly"] }))).toBe(false);
  });

  it("kişisel ilanda sigara ve hayvan kişinin kendi cevabıdır", () => {
    expect(matchesFilters(person(), withFilters({ lifestyle: ["noSmoke", "petFriendly"] }))).toBe(true);
    expect(matchesFilters(person({ owner_profile: owner({ smoking: true }) }), withFilters({ lifestyle: ["noSmoke"] }))).toBe(false);
    expect(matchesFilters(person({ owner_profile: owner({ pets: null }) }), withFilters({ lifestyle: ["petFriendly"] }))).toBe(false);
  });
});

describe("matchesFilters: diğer alanlar", () => {
  it("semt seçiliyse yalnızca o semtlerdeki ilanlar geçer", () => {
    const f = withFilters({ districts: ["Beşiktaş", "Sarıyer"] });
    expect(matchesFilters(house(), f)).toBe(false);
    expect(matchesFilters(house({ district: "Sarıyer" }), f)).toBe(true);
    expect(matchesFilters(house(), withFilters({ districts: [] }))).toBe(true);
  });

  it("ilan tipi", () => {
    expect(matchesFilters(house(), withFilters({ listingType: "kisisel_ilan" }))).toBe(false);
    expect(matchesFilters(person(), withFilters({ listingType: "kisisel_ilan" }))).toBe(true);
  });

  it("fiyat: ev ilanında kira, kişisel ilanda aralık kesişimi", () => {
    const f = withFilters({ priceRange: [5000, 10000] });
    expect(matchesFilters(house({ rent: 12000 }), f)).toBe(false);
    expect(matchesFilters(house({ rent: 9000 }), f)).toBe(true);
    expect(matchesFilters(person({ budget_min: 9500, budget_max: 15000 }), f)).toBe(true);
    expect(matchesFilters(person({ budget_min: 10500, budget_max: 15000 }), f)).toBe(false);
  });

  it("ev özellikleri yalnızca ev ilanına uygulanır", () => {
    const f = withFilters({ features: ["elevator"] });
    expect(matchesFilters(house(), f)).toBe(false);
    expect(matchesFilters(house({ elevator: true }), f)).toBe(true);
    expect(matchesFilters(person(), f)).toBe(true);
  });
});

describe("isDefaultFilters", () => {
  it("yalnızca hiçbir şey seçilmemişse doğru", () => {
    expect(isDefaultFilters(defaultFilters)).toBe(true);
    expect(isDefaultFilters(withFilters({ districts: ["Kadıköy"] }))).toBe(false);
    expect(isDefaultFilters(withFilters({ lifestyle: ["noAlcohol"] }))).toBe(false);
  });
});

describe("fiyat dağılımı", () => {
  it("az ilanda çizilmez", () => {
    expect(priceHistogram([10000, 12000, 14000])).toEqual([]);
  });

  it("gerçek fiyatları sayar, aralık dışını uca koyar", () => {
    const bins = priceHistogram([1000, 1500, 15000, 29999, 80000], 29);
    expect(bins).toHaveLength(29);
    expect(bins.reduce((a, b) => a + b, 0)).toBe(5);
    expect(bins[0]).toBe(2);
    expect(bins[14]).toBe(1);
    expect(bins[28]).toBe(2);
  });

  it("ilanın fiyatı: kira ya da bütçe ortası", () => {
    expect(listingPrice(house({ rent: 9000 }))).toBe(9000);
    expect(listingPrice(person({ budget_min: 8000, budget_max: 12000 }))).toBe(10000);
    expect(listingPrice(person({ budget_min: undefined }))).toBeNull();
  });
});
