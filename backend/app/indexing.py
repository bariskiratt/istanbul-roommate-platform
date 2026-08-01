"""Kira tahminlerini bugüne taşıyan TÜFE endekslemesi.

Eğitim verisinin fiyat düzeyi 2025 Şubat'tır (DATA_PERIOD). CSV'de tarih
kolonu yoktur; dönem veri setinin toplandığı tarihe dayanır. Model o dönemin
liralarıyla konuşur, kullanıcıya bugünün düzeyiyle gösterilmesi gerekir.

ÇARPAN NASIL BULUNDU (TÜİK haber bültenleri, doğrulanabilir):

TÜİK endeksi 2025'te yeniden tabanlandı — Şubat 2025 bülteni 2003=100,
Haziran 2026 bülteni 2025=100 kullanıyor. Bu yüzden iki bültenin endeks
SEVİYELERİ doğrudan bölünemez; oranlar zincirlenir:

    Şubat 2025,  Aralık 2024'e göre        : +%7,42   (Sayı 54177)
    Haziran 2025, Aralık 2024'e göre       : +%16,67  (Sayı 58289, karşılaştırma sütunu)
    Haziran 2026, Haziran 2025'e göre      : +%32,11  (Sayı 58289)

    Şubat 2025 → Haziran 2025 = 1,1667 / 1,0742 = 1,086111
    Şubat 2025 → Haziran 2026 = 1,086111 × 1,3211 = 1,434861

Bu 1,4349 manşet TÜFE'dir ve kira için ALT SINIRDIR. İki sebeple:
  1. Konut ana grubu manşetin belirgin üstünde arttı — Haziran 2026'da yıllık
     %45,14 (manşet %32,11), Şubat 2025'te %70,81 (manşet %39,05).
  2. TÜİK'in kira kalemi MEVCUT kiracıların ödediği kirayı ölçer; bunlar
     yıllarca yasal artış tavanına tabiydi. Bizim veri setimiz İLAN (istenen)
     kiralarıdır ve tavandan bağımsız hareket eder.

KULLANILAN ÇARPAN — konut ana grubuna dayalı, KISMEN TAHMİN:

Konut için Şubat→Haziran 2025 aralığı TÜİK bültenlerinde yayımlanmadığından
zincir tamamlanamıyor; sınırlandırılıyor:

    konut Haziran 2026 / Haziran 2025 = 1,4514                    (yayımlanmış)
    konut Şubat 2025 → Haziran 2025   = 1,0861 … 1,1962           (sınırlar)
        alt sınır: manşet TÜFE ile aynı hızda gitmesi
                   (konut o dönem hep manşetin üstündeydi, gerçekçi taban)
        üst sınır: Şubat 2025'in konut aylık oranının (+%4,58) dört ay sürmesi

    ⇒ konut Şubat 2025 → Haziran 2026 = 1,576 … 1,736   orta nokta 1,656

ANCHOR_FACTOR bu bandın ortasına yuvarlanmıştır. Manşet TÜFE'nin (1,4349)
%16 üstünde. YAYIMLANMIŞ BİR SAYI DEĞİLDİR — yukarıdaki sınırlardan
türetilmiş bir tahmindir; HEADLINE_FACTOR kesin olanı saklar ki karar
denetlenebilsin ve gerekirse geri dönülebilsin.

Piyasa gözlemi bunu yanlışlarsa RENT_INDEX_FACTOR ile koda dokunmadan ezilir.

GÜNCELLEME: her yeni TÜİK bülteninde MONTHLY_AFTER_ANCHOR'a tek satır ekle
(bültenin ilk sayfasındaki konut ya da manşet "bir önceki aya göre" oranı).
Taban değişmediği sürece çıpayı yeniden hesaplamak gerekmez.
"""

import os

# Eğitim verisinin fiyat düzeyi (yıl-ay).
DATA_PERIOD = "2025-02"

# Manşet TÜFE zincirinden KESİN olarak türetilen çarpan (alt sınır).
# Kullanılmıyor ama kaynak denetlenebilsin diye duruyor; testte doğrulanıyor.
HEADLINE_FACTOR = 1.434861

# Servis edilen çıpa: konut ana grubuna dayalı, bandın ortası (bkz. başlık).
ANCHOR_PERIOD = "2026-06"
ANCHOR_FACTOR = 1.656

# ANCHOR_PERIOD'dan SONRAKİ aylar (%, bir önceki aya göre; TÜİK bülteni).
# Örn. Temmuz 2026 bülteni çıkınca:  "2026-07": <aylık oran>
MONTHLY_AFTER_ANCHOR: dict[str, float] = {}


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
