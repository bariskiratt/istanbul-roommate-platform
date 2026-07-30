"""Kira tahminlerini bugüne taşıyan TÜFE endekslemesi.

Eğitim verisi 2026 başı fiyat düzeyini yansıtıyor (CSV'de tarih kolonu yok;
dönem proje sahibinin bilgisine dayanıyor). Model çıktısı o dönemin
liralarıyla konuşur; kullanıcıya gösterirken TÜİK aylık TÜFE artışlarıyla
bugünün düzeyine çekiyoruz.

Yeni ay açıklandığında MONTHLY_CPI'a tek satır eklemek yeterli.
Kaynak: TÜİK Tüketici Fiyat Endeksi haber bültenleri (veriportali.tuik.gov.tr).
"""

import os

# Eğitim verisinin fiyat düzeyi (yıl-ay)
DATA_PERIOD = "2026-01"

# TÜİK aylık TÜFE artışları (%, bir önceki aya göre)
MONTHLY_CPI: dict[str, float] = {
    "2026-02": 2.96,
    "2026-03": 1.94,
    "2026-04": 4.18,
    "2026-05": 1.71,
    "2026-06": 0.99,
}


def rent_index() -> tuple[float, str]:
    """(birikimli çarpan, endekslenen son ay) döndürür.

    RENT_INDEX_FACTOR ortam değişkeni verilirse tablo yerine o kullanılır
    (ör. testte sabitlemek ya da acil düzeltme için).
    """
    override = os.getenv("RENT_INDEX_FACTOR")
    if override:
        return float(override), "manuel"

    factor = 1.0
    last = DATA_PERIOD
    for month in sorted(MONTHLY_CPI):
        if month > DATA_PERIOD:
            factor *= 1 + MONTHLY_CPI[month] / 100
            last = month
    return factor, last
