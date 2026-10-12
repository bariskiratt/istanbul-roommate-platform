/**
 * Hinge tarzı soru-cevap kartları: profilde ve destede fotoğrafların arasına
 * giren "Uyku düzenim: Gece kuşuyum" gibi kartlar.
 *
 * Kimse ayrıca soru cevaplamaz; kartlar kişinin onboarding'de ve ilan
 * formunda ZATEN verdiği bilgiden üretilir. Alan boşsa kart da yoktur —
 * bilinmeyen bir şey varsayılanla doldurulup kişinin ağzından yazılmaz.
 *
 * Saf fonksiyonlar: çeviri (`t`), sayı biçimi (`n`) ve yerel ayar dışarıdan
 * gelir, böylece testte React olmadan çalışır (src/test/prompts.test.ts).
 */

import type { TranslationKey } from "@/i18n/translations";
import {
  LISTING_FEATURES,
  type ApiListing,
  type ListingFeature,
  type PromptKey,
} from "@/lib/api";

/** Yalnızca gösterilen kartlar da var: Beğeniler ekranında beğeni verilmez. */
export type DisplayPromptKey = PromptKey | "budget" | "districts";

/** Beğenilebilen kartlar; sunucudaki PromptKey listesiyle aynı. */
const LIKABLE: readonly string[] = [
  "description",
  "sleep",
  "habits",
  "studies",
  "house_rules",
  "amenities",
] satisfies readonly PromptKey[];

export const isLikablePrompt = (key: string): key is PromptKey => LIKABLE.includes(key);

export interface Prompt {
  key: DisplayPromptKey;
  question: string;
  answer: string;
  /** Cevap ekrandaki en önemli rakamsa fosforlu kalemle basılır (bütçe). */
  marker?: boolean;
}

type Translate = (key: TranslationKey, vars?: Record<string, string | number>) => string;

export interface PromptContext {
  t: Translate;
  n: (value: number) => string;
  /** "tr-TR" | "en-US"; büyük/küçük harf Türkçe kuralıyla yapılsın diye. */
  locale: string;
}

/**
 * Kişinin kartlarına kaynak olan alanlar. PublicUser, ApiUser ve
 * OwnerProfile'ın ortak kısmı; olmayan alan kartı da olmayan alan demek.
 */
export interface PersonFields {
  department?: string | null;
  year?: number | null;
  sleep_schedule?: string | null;
  smoking?: boolean | null;
  pets?: boolean | null;
  alcohol?: boolean | null;
  budget_min?: number | null;
  budget_max?: number | null;
  preferred_districts?: string[] | null;
}

const capitalize = (text: string, locale: string) =>
  text ? text.charAt(0).toLocaleUpperCase(locale) + text.slice(1) : text;

/** "sigara içmem", "alkol kullanırım" → "Sigara içmem, alkol kullanırım." */
const sentence = (clauses: string[], locale: string) =>
  clauses.length ? `${capitalize(clauses.join(", "), locale)}.` : "";

const SLEEP: Record<string, TranslationKey> = {
  erken: "prompt.sleep.early",
  gece: "prompt.sleep.night",
  esnek: "prompt.sleep.flexible",
};

const FEATURE_LABELS: Record<ListingFeature, TranslationKey> = {
  furnished: "filter.furnished",
  elevator: "filter.elevator",
  parking: "filter.parking",
  internet_included: "filter.internet",
  heating_included: "filter.heating",
  balcony: "filter.balcony",
  natural_gas: "filter.gas",
};

const yesNo = (
  value: boolean | null | undefined,
  yes: TranslationKey,
  no: TranslationKey,
  t: Translate,
): string | null => (value === true ? t(yes) : value === false ? t(no) : null);

/** Uyku düzeni, alışkanlıklar ve bölüm — destede ilan sahibinde de görünenler. */
export const roommatePrompts = (p: PersonFields, { t, locale }: PromptContext): Prompt[] => {
  const prompts: Prompt[] = [];

  const sleepKey = p.sleep_schedule ? SLEEP[p.sleep_schedule] : undefined;
  if (sleepKey) {
    prompts.push({ key: "sleep", question: t("prompt.q.sleep"), answer: t(sleepKey) });
  }

  const habits = [
    yesNo(p.smoking, "prompt.habits.smokes", "prompt.habits.noSmoke", t),
    yesNo(p.alcohol, "prompt.habits.drinks", "prompt.habits.noDrinks", t),
    yesNo(p.pets, "prompt.habits.pets", "prompt.habits.noPets", t),
  ].filter((c): c is string => c !== null);
  if (habits.length) {
    prompts.push({ key: "habits", question: t("prompt.q.habits"), answer: sentence(habits, locale) });
  }

  if (p.department) {
    const answer = p.year ? `${p.department}, ${t("likes.year", { year: p.year })}` : p.department;
    prompts.push({ key: "studies", question: t("prompt.q.studies"), answer });
  }

  return prompts;
};

/**
 * Kişinin tam kart dizisi (Beğeniler ve kendi profil önizlemesi): ev arkadaşı
 * kartlarına ek olarak bütçe ve semt tercihleri. Bütçe, o ekrandaki en önemli
 * rakam olduğu için fosforlu kalemle basılır.
 */
export const personPrompts = (p: PersonFields, ctx: PromptContext): Prompt[] => {
  const { t, n } = ctx;
  const prompts = roommatePrompts(p, ctx);

  if (p.budget_min && p.budget_max) {
    prompts.push({
      key: "budget",
      question: t("prompt.q.budget"),
      answer: `${n(p.budget_min)}–${n(p.budget_max)} TL${t("common.perMonth")}`,
      marker: true,
    });
  }

  if (p.preferred_districts?.length) {
    prompts.push({
      key: "districts",
      question: t("prompt.q.districts"),
      answer: p.preferred_districts.join(", "),
    });
  }

  return prompts;
};

/** Ev ilanının kendi kartları: kurallar ve evde olanlar. Kişisel ilanda yok. */
export const housePrompts = (l: ApiListing, { t, locale }: PromptContext): Prompt[] => {
  if (l.type !== "ev_ilani") return [];
  const prompts: Prompt[] = [];

  const rules = [
    yesNo(l.smoking_allowed, "prompt.rules.smoking", "prompt.rules.noSmoking", t),
    yesNo(l.pets_allowed, "prompt.rules.pets", "prompt.rules.noPets", t),
  ].filter((c): c is string => c !== null);
  if (rules.length) {
    prompts.push({ key: "house_rules", question: t("prompt.q.house_rules"), answer: sentence(rules, locale) });
  }

  // Yalnızca açıkça "var" denenler; null "bilinmiyor" demektir (filtreyle aynı kural).
  const features = LISTING_FEATURES.filter(key => l[key] === true).map(key =>
    t(FEATURE_LABELS[key]).toLocaleLowerCase(locale),
  );
  if (features.length) {
    prompts.push({ key: "amenities", question: t("prompt.q.amenities"), answer: sentence(features, locale) });
  }

  return prompts;
};

/**
 * Destedeki ilan kartının kartları: önce evin kendisi, sonra ev arkadaşı
 * olacak kişi. Hepsi beğenilebilir; anahtarlar sunucunun listesindendir.
 */
export const listingPrompts = (l: ApiListing, ctx: PromptContext): Prompt[] => [
  ...housePrompts(l, ctx),
  ...(l.owner_profile ? roommatePrompts(l.owner_profile, ctx) : []),
];

export type TimelineItem =
  | { kind: "photo"; url: string; /** İlandaki/profildeki asıl sırası. */ index: number }
  | { kind: "prompt"; prompt: Prompt };

/**
 * Hinge'in profil düzeni: kart, fotoğraf, kart, fotoğraf… Kapak fotoğrafı
 * ayrı basıldığı için dizi KARTLA başlar; biri tükenince diğerinin kalanı
 * arkaya eklenir. `firstIndex`, `photos`un asıl dizideki başlangıç sırasıdır
 * (kapak çıkarıldıysa 1): fotoğraf beğenisi sunucuya bu sırayla gider.
 */
export const interleave = (photos: string[], prompts: Prompt[], firstIndex = 0): TimelineItem[] => {
  const items: TimelineItem[] = [];
  for (let i = 0; i < Math.max(photos.length, prompts.length); i++) {
    if (i < prompts.length) items.push({ kind: "prompt", prompt: prompts[i] });
    if (i < photos.length) items.push({ kind: "photo", url: photos[i], index: firstIndex + i });
  }
  return items;
};

/**
 * Beğenilen kartın metni — beğeniyi ALAN kişinin ekranı için. Kart, alanın
 * KENDİ verisinden (profil + ilan) bugünkü hâliyle yeniden üretilir; kart
 * artık yoksa (alan boşaltıldı, ilan kapandı) yalnızca soru gösterilir.
 */
export const describeLikedPrompt = (
  key: string,
  me: PersonFields,
  listing: ApiListing | undefined,
  ctx: PromptContext,
): { question: string; answer: string | null } | null => {
  if (key === "description") {
    return { question: ctx.t("prompt.q.description"), answer: listing?.description ?? null };
  }
  const all = [...(listing ? housePrompts(listing, ctx) : []), ...roommatePrompts(me, ctx)];
  const found = all.find(p => p.key === key);
  if (found) return { question: found.question, answer: found.answer };
  return isLikablePrompt(key)
    ? { question: ctx.t(`prompt.q.${key}` as TranslationKey), answer: null }
    : null;
};
