"""Türkçe adres metinlerini eşleştirme için normalize eder.

CSV ("Kartaltepe Mah.") ile GeoJSON ("Kartaltepe Mahallesi") arasındaki
isim farklarını ortadan kaldırmak için tek bir kanonik biçim üretir.
"""

import re

# Python'un str.upper() metodu Türkçe'de hatalıdır: 'i' -> 'I' (olması gereken 'İ').
# Bu yüzden aksanları ASCII'ye katlayıp öyle büyütüyoruz; her iki taraf da aynı
# dönüşümden geçtiği için eşleşme tutarlı oluyor.
_TR_FOLD = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i", "İ": "i", "i": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
    "â": "a", "Â": "a",
    "î": "i", "Î": "i",
    "û": "u", "Û": "u",
})

# "Mah.", "Mahallesi", "Mh." gibi ekler iki veri kaynağında farklı yazılıyor.
_SUFFIX_RE = re.compile(r"\b(mahallesi|mahalle|mah|mh)\.?\s*$")
_WS_RE = re.compile(r"\s+")

# GeoJSON'da mahalle adı bu alanlardan birinde, ilçe adı diğerinde tutuluyor.
# Sıra önemli: en spesifik alan önce denenir.
NEIGHBORHOOD_FIELDS = ("suburb", "neighbourhood", "city", "village")
DISTRICT_FIELDS = ("town", "city_district", "archipelago", "county")


def fold(text) -> str:
    """Metni aksansız, küçük harfli, tek boşluklu kanonik biçime çevirir."""
    if not text:
        return ""
    folded = str(text).translate(_TR_FOLD).lower()
    return _WS_RE.sub(" ", folded).strip()


def norm_neighborhood(text) -> str:
    """Mahalle adını normalize eder ve "Mah./Mahallesi" ekini atar."""
    return _SUFFIX_RE.sub("", fold(text)).strip()


def norm_district(text) -> str:
    """İlçe adını normalize eder."""
    return fold(text)


def squash(text) -> str:
    """Boşlukları da atarak en toleranslı anahtarı üretir.

    İki kaynak aynı mahalleyi farklı bölerek yazabiliyor:
    "Emniyet Evleri" / "Emniyetevler", "İzzet Paşa" / "İzzetpaşa".
    """
    return norm_neighborhood(text).replace(" ", "")


def display_name(text) -> str:
    """Türkçe karakterleri koruyarak gösterime uygun ad üretir."""
    if not text:
        return ""
    cleaned = _WS_RE.sub(" ", str(text)).strip()
    # Sondaki "Mahallesi"/"Mah." ekini at (aksanları bozmadan).
    return re.sub(
        r"\s+(Mahallesi|Mahalle|Mah|Mh)\.?$", "", cleaned, flags=re.IGNORECASE
    ).strip()


def extract_place(address: dict) -> tuple[str, str]:
    """GeoJSON address sözlüğünden ham (mahalle, ilçe) çiftini çıkarır.

    Nominatim aynı bilgiyi kayda göre farklı anahtarlarda tutuyor
    (suburb/city/village/neighbourhood ve town/city_district/archipelago),
    bu yüzden hepsini sırayla deniyoruz. İlçe bulunamazsa "" döner ve
    çağıran taraf yalnızca mahalle adına göre eşleştirme yapabilir.
    """
    address = address or {}
    neighborhood = next(
        (address[f] for f in NEIGHBORHOOD_FIELDS if address.get(f)), ""
    )
    district = next((address[f] for f in DISTRICT_FIELDS if address.get(f)), "")
    return str(neighborhood), str(district)
