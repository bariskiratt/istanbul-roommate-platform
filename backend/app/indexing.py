"""Kira tahminlerini bugüne taşıyan kira endekslemesi.

Eğitim verisinin fiyat düzeyi 2025 Şubat'tır (DATA_PERIOD). CSV'de tarih
kolonu yoktur; dönem veri setinin toplandığı tarihe dayanır. Model o dönemin
liralarıyla konuşur, kullanıcıya bugünün düzeyiyle gösterilmesi gerekir.

KULLANILAN ENDEKS: TCMB Yeni Kiracı Kira Endeksi (YKKE), İSTANBUL (TR10).

Neden bu endeks (Ekim 2026'da TÜİK konut grubundan buna geçildi):
  1. Aynı şeyi ölçüyor: YENİ kiracıya verilen kira. Bizim veri setimiz de ilan
     (yeni sözleşme) kirasıdır. TÜİK'in kira kalemi ise MEVCUT kiracıların
     ödediğini ölçer; %25 tavanı 2024'te kalkınca eski sözleşmeler piyasaya
     yetişmeye başladı ve TÜİK kirası yeni kiraların ÜSTÜNE çıktı:
         Haziran 2025 → Haziran 2026, TÜİK konut ana grubu : +%45,14
         Haziran 2025 → Haziran 2026, YKKE İstanbul        : +%33,4
     Eski çıpa (1,656) bu yüzden İstanbul ilan kiralarını ~%7 fazla
     şişiriyordu.
  2. İstanbul'a özgü; TÜİK serisi Türkiye geneli.
  3. Hedonik (nitelik düzeltmeli): ayın evleri daha büyük/yeni diye endeks
     şişmez.
  4. Zincirin tamamı YAYIMLANMIŞ sayılardan kurulur, tahmin içermez (eski
     çıpanın Şubat→Haziran 2025 bacağı bir aralığın orta noktasıydı).

Zayıf yanı: veri kaynağı bankaların konut kredisi değerleme raporları,
yani kira değerini ekspertiz uzmanı biçer; ilan fiyatı değildir ve
kredilendirilebilir (daha yeni) konutlara kayabilir. TCMB YKKE'yi Şubat
2026'dan beri yayımlıyor; geçmiş değerleri revize edebilir.

ZİNCİR (her sayı TCMB'nin aylık "Konut Fiyat Endeksi ve Yeni Kiracı Kira
Endeksi" bülteninin İstanbul satırı):

    Şubat 2026, bir önceki yılın aynı ayına göre : +%41,0  → ANCHOR_FACTOR
        (Şubat 2025 → Şubat 2026 tam olarak veri dönemimizden başlar)
    Mart–Eylül 2026, bir önceki aya göre         : MONTHLY_AFTER_ANCHOR

    Şubat 2025 → Eylül 2026 = 1,410 × 1,022 × 1,014 × 1,031 × 1,025
                              × 1,017 × 1,049 × 1,035 = 1,7050

Sağlama: bültenlerdeki endeks seviyeleri (2023=100) Temmuz 309,4, Ağustos
324,9, Eylül 336,5. 309,4 × 1,049 × 1,035 = 335,9 → yayımlanan 336,5'ten
%0,2 sapma (yuvarlama + revizyon). Testte kontrol ediliyor.

KARŞILAŞTIRMA (kullanılmıyor, denetim için):
  - Manşet TÜFE, Şubat 2025 → Haziran 2026 = 1,4349 (HEADLINE_FACTOR; alt
    sınır, kira bundan hızlı arttı). TÜİK 2025'te tabanı değiştirdiği için
    oranlar zincirlenir:
        Şubat 2025, Aralık 2024'e göre        : +%7,42   (Sayı 54177)
        Haziran 2025, Aralık 2024'e göre      : +%16,67  (Sayı 58289, karşılaştırma sütunu)
        Haziran 2026, Haziran 2025'e göre     : +%32,11  (Sayı 58289)
  - Eski yöntem (Ağustos 2026): TÜİK konut ana grubu, Haziran 2026 çıpası
    1,656. Temmuz–Eylül 2026 konut aylıklarıyla (+%2,25, +%2,26, +%2,71)
    Eylül'e taşınsaydı 1,778 olurdu.

Piyasa gözlemi bunu yanlışlarsa RENT_INDEX_FACTOR ile koda dokunmadan ezilir.

GÜNCELLEME: TCMB her ayın ~16'sında bir önceki ayın bültenini yayımlar
(tcmb.gov.tr → İstatistikler → Konut Fiyat Endeksi). Bültendeki "YKKE ...
İstanbul, Ankara ve İzmir'de bir önceki aya göre sırasıyla yüzde X" cümlesinin
İstanbul (ilk) sayısını MONTHLY_AFTER_ANCHOR'a tek satır olarak ekle. Endeks
seviyesini ya da yıllık oranı değil, AYLIK oranı yaz.
"""

import os

# Eğitim verisinin fiyat düzeyi (yıl-ay).
DATA_PERIOD = "2025-02"

# Manşet TÜFE zincirinden kesin olarak türetilen Şubat 2025 → Haziran 2026
# çarpanı. Kullanılmıyor; kiranın manşetin üstünde arttığını denetlemek için.
HEADLINE_FACTOR = 1.434861

# Çıpa: YKKE İstanbul, Şubat 2026'nın bir önceki yılın aynı ayına göre
# değişimi (+%41,0). DATA_PERIOD'un tam 12 ay sonrası olmalı.
ANCHOR_PERIOD = "2026-02"
ANCHOR_FACTOR = 1.410

# ANCHOR_PERIOD'dan SONRAKİ aylar: YKKE İstanbul, bir önceki aya göre (%).
# Örn. Ekim 2026 bülteni çıkınca:  "2026-10": <aylık oran>,
MONTHLY_AFTER_ANCHOR: dict[str, float] = {
    "2026-03": 2.2,
    "2026-04": 1.4,
    "2026-05": 3.1,
    "2026-06": 2.5,
    "2026-07": 1.7,
    "2026-08": 4.9,
    "2026-09": 3.5,
}


def is_configured() -> bool:
    """Endeksleme yapılabilir durumda mı?"""
    return bool(os.getenv("RENT_INDEX_FACTOR")) or ANCHOR_FACTOR > 0


def rent_index() -> tuple[float, str]:
    """(çarpan, endekslenen dönem) döndürür.

    RENT_INDEX_FACTOR ortam değişkeni verilirse tablo yerine o kullanılır —
    koda dokunmadan acil düzeltme ya da testte sabitleme için.
    """
    override = os.getenv("RENT_INDEX_FACTOR")
    if override:
        try:
            return float(override), "manuel"
        except ValueError:
            pass  # bozuk değer /api/estimate'i düşürmesin; tabloya dön

    factor = ANCHOR_FACTOR
    last = ANCHOR_PERIOD
    for month in sorted(MONTHLY_AFTER_ANCHOR):
        if month > ANCHOR_PERIOD:
            factor *= 1 + MONTHLY_AFTER_ANCHOR[month] / 100
            last = month
    return factor, last
