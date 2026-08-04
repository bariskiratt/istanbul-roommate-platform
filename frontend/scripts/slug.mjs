/**
 * Semt adlarını URL parçasına çeviren tek kaynak.
 *
 * Ayrı dosyada, çünkü generate-seo.mjs import edilir edilmez tüm siteyi
 * üretiyor; testin yalnızca bu fonksiyona erişebilmesi gerekiyor.
 */

const TR_MAP = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", İ: "i", I: "i" };

/** "Kadıköy" -> "kadikoy" (URL için).
 *
 * SIRA ÖNEMLİ: önce küçült, sonra eşle. Tersi bir dönem üretimdeydi ve
 * BAŞ HARFİ Türkçe olan semtlerin o harfini tamamen yutuyordu — eşleme
 * tablosunda yalnızca küçük harfler var, "Ş" ıskalanıyor, ardından
 * küçültme onu "ş" yapıyor, [^a-z0-9] tireye çeviriyor, baştaki tire de
 * kırpılıyordu: "Şişli" -> "isli", "Üsküdar" -> "skudar".
 */
export function slug(name) {
  return name
    .trim()
    .toLocaleLowerCase("tr")
    .replace(/[çğıöşüİI]/g, ch => TR_MAP[ch] ?? ch)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

/**
 * Slug adın HİÇBİR harfini düşürmemeli.
 *
 * Yukarıdaki hata sessizdi: "skudar" geçerli bir slug'a benziyor, benzersiz
 * ve boş değil, o yüzden "benzersiz mi / dolu mu" türü bir kontrol onu
 * yakalayamazdı. Harf sayısını karşılaştırmak eşlenmemiş HER karakteri
 * yakalar, yalnızca baş harf durumunu değil.
 */
export function slugDropsCharacters(name) {
  const harfler = name.replace(/[^\p{L}\p{N}]/gu, "").length;
  return slug(name).replace(/-/g, "").length !== harfler;
}
