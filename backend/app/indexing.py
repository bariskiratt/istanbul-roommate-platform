"""Kira tahminlerini bugüne taşıyan endeksleme.

Eğitim verisinin fiyat düzeyi 2025 Şubat'tır. CSV'de tarih kolonu yoktur;
dönem veri setinin toplandığı tarihe dayanır (DATA_PERIOD). Model o dönemin
liralarıyla konuşur, kullanıcıya bugünün düzeyiyle göstermek gerekir.

YÖNTEM — neden aylık yüzde değil, endeks SEVİYESİ:
Önceki sürüm aylık TÜFE yüzdelerini tek tek tabloya yazıp çarpıyordu. Bu
yaklaşım iki yönden kırılgan: (1) her ay elle bir satır eklenmesi gerekir ve
unutulursa tahminler sessizce geride kalır, (2) on sekiz ayı tek tek girmek
hem hataya açıktır hem de sonucu doğrulamak zordur. Bunun yerine iki endeks
seviyesi kullanılır ve çarpan tek bölmeyle bulunur:

    çarpan = ENDEKS[bugün] / ENDEKS[DATA_PERIOD]

İki sayı da TÜİK'ten doğrudan okunur ve sonuç kolayca denetlenir.

HANGİ ENDEKS: Konut kirası, Türkiye'de genel TÜFE'den belirgin biçimde hızlı
artmıştır; manşet TÜFE kullanmak kiraları olduğundan düşük gösterir. Bu yüzden
TÜFE'nin "gerçek kira" alt kalemi tercih edilmelidir (TÜİK veri portalı →
Tüketici Fiyat Endeksi → madde bazında endeks).

YAPILANDIRILMAMIŞSA: çarpan 1.0'dır ve tahminler DATA_PERIOD düzeyinde kalır.
Bu durum API yanıtında `indexed: false` ile bildirilir ve arayüz "endekslenmedi"
yazar — sessizce yanlış fiyat göstermek yerine görünür biçimde eksik kalır.
"""

import os

# Eğitim verisinin fiyat düzeyi (yıl-ay). Veri setinin toplandığı dönem.
DATA_PERIOD = "2025-02"

# TÜİK endeks seviyeleri (aylık yüzde DEĞİL, endeksin kendisi).
# En az iki giriş gerekir: DATA_PERIOD ve en güncel ay.
#
#   RENT_INDEX = {
#       "2025-02": <TÜİK endeksi>,
#       "2026-07": <TÜİK endeksi>,
#   }
#
# Boş bırakıldığı sürece endeksleme yapılmaz (bkz. modül başlığı).
RENT_INDEX: dict[str, float] = {}

_warned = False


def _warn_once(message: str) -> None:
    global _warned
    if not _warned:
        print(message, flush=True)
        _warned = True


def is_configured() -> bool:
    """Endeksleme yapılabilir durumda mı?"""
    if os.getenv("RENT_INDEX_FACTOR"):
        return True
    return DATA_PERIOD in RENT_INDEX and len(RENT_INDEX) >= 2


def rent_index() -> tuple[float, str]:
    """(çarpan, endekslenen dönem) döndürür.

    RENT_INDEX_FACTOR ortam değişkeni verilirse tablo yerine o kullanılır —
    tabloya dokunmadan acil düzeltme ya da testte sabitleme için.
    """
    override = os.getenv("RENT_INDEX_FACTOR")
    if override:
        try:
            return float(override), "manuel"
        except ValueError:
            pass  # bozuk değer /api/estimate'i düşürmesin; tabloya dön

    base = RENT_INDEX.get(DATA_PERIOD)
    if not base:
        _warn_once(
            "⚠️  Kira endeksi yapılandırılmamış — tahminler "
            f"{DATA_PERIOD} fiyat düzeyinde kalıyor ve bugünkü kiraların "
            "altında görünecek. app/indexing.py içindeki RENT_INDEX tablosuna "
            "TÜİK endeks seviyelerini girin."
        )
        return 1.0, DATA_PERIOD

    latest = max(RENT_INDEX)
    return RENT_INDEX[latest] / base, latest
