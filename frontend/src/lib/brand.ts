/**
 * Görünen marka adı — tek kaynak.
 *
 * Ad beş ayrı dosyada elle yazılmıştı; biri güncellenmeden kalınca site
 * kendini iki isimle tanıtıyordu. Arama motorunun markayı öğrenmesi de,
 * insanların adı hatırlaması da tek bir ada bağlı.
 *
 * ".tr" bilerek adın parçası: "evdes" tek başına T.C. Enerji Bakanlığı'nın
 * EVDES sistemiyle ve "evdeş" sözlük kelimesiyle çakışıyor, o aramalarda
 * uzun süre görünmeyiz. "evdes.tr" hem ayırt edici hem de kullanıcının
 * adres çubuğuna yazacağı şeyin aynısı.
 *
 * DİKKAT: bu yalnızca GÖRÜNEN ad. Depolanan anahtar (localStorage
 * "roommatch_token") bilerek eski adında bırakıldı — değiştirmek herkesin
 * oturumunu düşürür.
 */
export const BRAND = "evdes.tr";
