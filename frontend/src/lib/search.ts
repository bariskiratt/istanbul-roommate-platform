/**
 * Türkçe karakterlere duyarsız metin arama yardımcıları.
 *
 * Kullanıcı klavyesinde Türkçe harf olmayabilir ya da acele ederken kullanmaz:
 * "besiktas" yazan biri Beşiktaş'ı, "cafer" yazan biri "Caferağa Mah."ı
 * bulabilmeli. Bu yüzden hem arama metni hem aday metin aynı sadeleştirmeden
 * geçirilip öyle karşılaştırılır.
 *
 * Saf fonksiyonlardır — React'e ya da API'ye bağlı değildir, test edilebilir.
 */

/**
 * Unicode ayrıştırmasının (NFD) çözemediği ya da yanlış çözdüğü harfler.
 * "ı" (noktasız i) hiç ayrışmaz; "İ" ayrışır ama küçültme sırası locale'e göre
 * değişebilir. Bunları elle eşlemek davranışı locale'den bağımsız kılar.
 */
const TR_CHARS: Record<string, string> = {
  ı: "i", İ: "i", I: "i", i: "i",
  ş: "s", Ş: "s",
  ğ: "g", Ğ: "g",
  ü: "u", Ü: "u",
  ö: "o", Ö: "o",
  ç: "c", Ç: "c",
  â: "a", Â: "a",
  î: "i", Î: "i",
  û: "u", Û: "u",
};

/**
 * Metni karşılaştırılabilir hâle getirir: Türkçe harfler ASCII karşılığına
 * iner, kalan aksanlar (é, ñ …) ayrıştırılıp atılır, sonuç küçük harf olur.
 *
 * normalizeText("Beşiktaş") === "besiktas"
 * normalizeText("Caferağa Mah.") === "caferaga mah."
 */
export const normalizeText = (value: string): string =>
  value
    .replace(/[ıİIişŞğĞüÜöÖçÇâÂîÎûÛ]/g, ch => TR_CHARS[ch])
    .toLowerCase()
    // Geriye kalan aksanlı harfleri (Türkçe olmayanlar) taban harfe indirger.
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");

/**
 * `text` arama sorgusuyla eşleşiyor mu.
 *
 * Sorgu boşluklarla bölünür ve TÜM parçalar metinde geçmelidir; böylece
 * "kadikoy cafer" gibi iki kelimelik aramalar da çalışır. Boş sorgu her şeyle
 * eşleşir (filtre uygulanmamış sayılır).
 */
export const matchesQuery = (text: string, query: string): boolean => {
  const tokens = normalizeText(query).split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return true;
  const haystack = normalizeText(text);
  return tokens.every(token => haystack.includes(token));
};

/** `matchesQuery` ile liste süzer; `getText` her öğenin aranacak metnini verir. */
export const filterByQuery = <T>(
  items: readonly T[],
  query: string,
  getText: (item: T) => string,
): T[] => items.filter(item => matchesQuery(getText(item), query));
