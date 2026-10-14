/**
 * Destedeki filtrelerin kuralları (FilterModal seçer, SwipeScreen uygular).
 *
 * Saf fonksiyonlar; React'e bağlı değil, src/test/deckFilters.test.ts
 * doğrudan test ediyor.
 *
 * TEMEL KURAL: filtre yalnızca kartta zaten görünen veriye bakar. İlan
 * sahibinin bütçesi, semt tercihleri, biyografisi, cinsiyeti ve yaşı
 * destede BİLEREK gizli (beğeniden sonra açılır); sunucu bunları göndermiyor,
 * filtre de onlara dayanamaz. Eskiden cinsiyet ve "temiz / sosyal / sessiz"
 * çipleri vardı ama arkalarında veri yoktu; alkol ve uyku çipleri de sahibin
 * profili "anon" yer tutucusuyla değiştirildiği için hiçbir şey yapmıyordu.
 * Kullanıcı filtrelediğini sanıyordu.
 */
import type { ApiListing, ListingFeature } from "./api";

/** Yaşam tarzı çipleri. Değer, filtrenin kimliğidir (ekrandaki etiket ayrı). */
export const LIFESTYLE_FILTERS = [
  "noSmoke",
  "petFriendly",
  "noAlcohol",
  "earlyBird",
  "nightOwl",
] as const;
export type LifestyleFilter = (typeof LIFESTYLE_FILTERS)[number];

export type ListingTypeFilter = "all" | ApiListing["type"];

export interface ListingFilters {
  listingType: ListingTypeFilter;
  priceRange: [number, number];
  rooms: number;
  lifestyle: LifestyleFilter[];
  /** Backend `features` parametresiyle aynı anahtarlar. */
  features: ListingFeature[];
  /** Boşsa semt filtresi yok; doluysa ilan bu ilçelerden birinde olmalı. */
  districts: string[];
}

export const PRICE_MIN = 1000;
export const PRICE_MAX = 30000;

export const defaultFilters: ListingFilters = {
  listingType: "all",
  priceRange: [PRICE_MIN, PRICE_MAX],
  rooms: 0,
  lifestyle: [],
  features: [],
  districts: [],
};

/** Seçim varsayılanla aynı mı (yani gerçekte hiçbir filtre yok mu)? */
export const isDefaultFilters = (f: ListingFilters): boolean =>
  f.listingType === defaultFilters.listingType &&
  f.priceRange[0] === defaultFilters.priceRange[0] &&
  f.priceRange[1] === defaultFilters.priceRange[1] &&
  f.rooms === defaultFilters.rooms &&
  f.lifestyle.length === 0 &&
  f.features.length === 0 &&
  f.districts.length === 0;

/**
 * Yaşam tarzı çipinin ilanda karşılığı.
 *
 * - Sigara ve hayvan, ev ilanında EVİN KURALIDIR (smoking_allowed,
 *   pets_allowed); kişisel ilanda ilanı verenin kendi cevabı.
 * - Alkol ve uyku düzeni her iki türde de ilanı veren KİŞİNİN cevabıdır
 *   (owner_profile): ev ilanında birlikte yaşayacağın kişi odur.
 *
 * Bilinmeyen (null / profil yok) eşleşme SAYILMAZ: ev özellikleri
 * filtresiyle aynı kural. "Alkol kullanmaz" diyen kullanıcıya cevabı
 * bilinmeyen kişiyi göstermek, filtreyi yine sessizce etkisiz kılardı.
 */
const matchesLifestyle = (l: ApiListing, chip: LifestyleFilter): boolean => {
  const owner = l.owner_profile ?? null;
  const isHouse = l.type === "ev_ilani";
  switch (chip) {
    case "noSmoke":
      return isHouse ? l.smoking_allowed === false : owner?.smoking === false;
    case "petFriendly":
      return isHouse ? l.pets_allowed === true : owner?.pets === true;
    case "noAlcohol":
      return owner?.alcohol === false;
    case "earlyBird":
      return owner?.sleep_schedule === "erken";
    case "nightOwl":
      return owner?.sleep_schedule === "gece";
  }
};

export const matchesFilters = (l: ApiListing, f: ListingFilters): boolean => {
  if (f.listingType !== "all" && l.type !== f.listingType) return false;

  if (f.districts.length > 0 && !f.districts.includes(l.district)) return false;

  // Ev ilanında kira, kişisel ilanda bütçe aralığı kesişimi.
  // Varsayılan aralığa dokunulmadıysa "filtre yok" demektir; aksi halde
  // aralık dışındaki ilanlar kullanıcı istemeden elenirdi.
  const [min, max] = f.priceRange;
  const rangeTouched = min !== PRICE_MIN || max !== PRICE_MAX;
  if (rangeTouched) {
    if (l.type === "ev_ilani") {
      if (l.rent != null && (l.rent < min || l.rent > max)) return false;
    } else if (l.budget_min != null && l.budget_max != null) {
      if (l.budget_max < min || l.budget_min > max) return false;
    }
  }

  if (f.rooms > 0 && (!l.room_count || parseInt(l.room_count) < f.rooms)) return false;

  // Ev özellikleri: yalnızca ilanda açıkça "var" diyen alanlar geçer;
  // bilinmeyen (null) alan eşleşme sayılmaz — sunucudaki `features`
  // filtresiyle aynı kural. Koşul yalnızca ev ilanlarına uygulanır: kişisel
  // ilanda (ev arayan kişi) asansör/otopark gibi alanlar hiç olamayacağı için
  // filtre onları elemek yerine kapsam dışı bırakır — sunucu da böyle yapıyor.
  if (l.type === "ev_ilani") {
    for (const key of f.features) {
      if (l[key] !== true) return false;
    }
  }

  return f.lifestyle.every(chip => matchesLifestyle(l, chip));
};

/**
 * Fiyat çubuğunun arkasındaki dağılım için ilanın tek fiyatı: ev ilanında
 * kira, kişisel ilanda bütçe aralığının ortası. Bilinmiyorsa null.
 */
export const listingPrice = (l: ApiListing): number | null => {
  if (l.type === "ev_ilani") return l.rent ?? null;
  if (l.budget_min != null && l.budget_max != null) return (l.budget_min + l.budget_max) / 2;
  return null;
};

/** Bu kadar fiyat yoksa dağılım çizilmez: üç ilanın "dağılımı" yanıltır. */
export const MIN_HISTOGRAM_PRICES = 5;

/**
 * Gerçek ilan fiyatlarından [PRICE_MIN, PRICE_MAX] aralığında eşit genişlikte
 * kutular. Aralık dışındaki fiyat en yakın uç kutuya sayılır. Yeterli veri
 * yoksa boş dizi döner ve arayüz dağılımı hiç çizmez.
 */
export const priceHistogram = (prices: number[], bins = 30): number[] => {
  if (prices.length < MIN_HISTOGRAM_PRICES) return [];
  const counts = new Array<number>(bins).fill(0);
  const width = (PRICE_MAX - PRICE_MIN) / bins;
  for (const p of prices) {
    const i = Math.floor((p - PRICE_MIN) / width);
    counts[Math.min(bins - 1, Math.max(0, i))] += 1;
  }
  return counts;
};
