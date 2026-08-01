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
