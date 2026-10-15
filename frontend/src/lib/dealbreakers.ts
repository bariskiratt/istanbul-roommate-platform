/**
 * İstemediklerim: kişinin ev arkadaşında kesinlikle istemediği özellikler.
 *
 * Eleme SUNUCUDA yapılır (backend/app/dealbreakers.py): seçilen özelliği
 * taşıyan kişinin ilanı desteye ve ilan listesine hiç gelmez, beğenisi de
 * Beğeniler'e düşmez. Kural iki yönlüdür: o kişiler de senin ilanını görmez.
 * Burada yalnızca kapalı liste ve formun yardımcıları var.
 */

/** Sunucudaki kapalı listeyle aynı anahtarlar ve aynı sıra. */
export const DEALBREAKERS = ["smoking", "alcohol", "pets", "night_owl", "early_bird"] as const;
export type Dealbreaker = (typeof DEALBREAKERS)[number];

/**
 * Bilinmeyen ve tekrar eden anahtarları atar; sonuç listedeki sırayla döner.
 * Eski bir taslak ya da eski sunucu yanıtı formu bozmasın diye.
 */
export const normalizeDealbreakers = (values: readonly unknown[] | null | undefined): Dealbreaker[] =>
  DEALBREAKERS.filter(key => values?.includes(key) ?? false);

/** Seçiliyse çıkarır, değilse ekler. */
export const toggleDealbreaker = (values: readonly Dealbreaker[], key: Dealbreaker): Dealbreaker[] =>
  normalizeDealbreakers(values.includes(key) ? values.filter(v => v !== key) : [...values, key]);
