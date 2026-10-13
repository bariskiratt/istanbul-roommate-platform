/**
 * İstanbul'un 39 ilçesi — YALNIZCA yedek liste.
 *
 * İlçe ve mahalle listesinin asıl kaynağı `GET /api/locations`; oradan gelen
 * liste fiyat modelinin tanıdığı mahallelerle süzülüdür. Ancak hem kayıt
 * akışı hem ilan verme o uca bağlandığından, uç düşerse kullanıcı hiçbir
 * şey yapamaz hâle geliyordu. Bu liste o durumda devreye girer: mahalle
 * seçilemez (tahmin ilçe geneline düşer) ama akış tıkanmaz.
 *
 * Fiyat verisi taşımadığı için güncel kalması gerekmez; ilçe sayısı yıllardır
 * sabittir.
 */
export const FALLBACK_DISTRICTS: readonly string[] = [
  "Adalar", "Arnavutköy", "Ataşehir", "Avcılar", "Bağcılar", "Bahçelievler",
  "Bakırköy", "Başakşehir", "Bayrampaşa", "Beşiktaş", "Beykoz", "Beylikdüzü",
  "Beyoğlu", "Büyükçekmece", "Çatalca", "Çekmeköy", "Esenler", "Esenyurt",
  "Eyüpsultan", "Fatih", "Gaziosmanpaşa", "Güngören", "Kadıköy", "Kâğıthane",
  "Kartal", "Küçükçekmece", "Maltepe", "Pendik", "Sancaktepe", "Sarıyer",
  "Silivri", "Sultanbeyli", "Sultangazi", "Şile", "Şişli", "Tuzla",
  "Ümraniye", "Üsküdar", "Zeytinburnu",
];

/**
 * Ana sayfanın alt bilgisinden bağlantı verilen semt sayfaları (/semt/<slug>,
 * derlemede scripts/generate-seo.mjs üretir). Öğrencilerin en çok aradığı
 * semtler.
 *
 * NEDEN: Search Console semt sayfalarının çoğunu "keşfedildi, dizine
 * eklenmedi" diye gösteriyordu: Google adresleri site haritasından biliyor
 * ama ziyaret etmeye değer bulmuyordu. Ana sayfadan doğrudan bağlantı alan
 * sayfa, iki tık derindekinden daha önce taranır.
 *
 * Slug'ın sayfası gerçekten var mı ve slug() ile aynı mı:
 * src/test/districtLinks.test.ts.
 */
export const LINKED_DISTRICT_PAGES: readonly (readonly [name: string, slug: string])[] = [
  ["Kadıköy", "kadikoy"],
  ["Beşiktaş", "besiktas"],
  ["Şişli", "sisli"],
  ["Üsküdar", "uskudar"],
  ["Beyoğlu", "beyoglu"],
  ["Sarıyer", "sariyer"],
  ["Fatih", "fatih"],
  ["Ataşehir", "atasehir"],
  ["Bakırköy", "bakirkoy"],
  ["Maltepe", "maltepe"],
  ["Kağıthane", "kagithane"],
  ["Esenyurt", "esenyurt"],
];
