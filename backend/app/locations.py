"""İlan formunun kullandığı ilçe → mahalle listesi.

Kaynak İKİ dosyanın kesişimidir ve bunun bir nedeni var:

- `data/processed/neighborhood_market_values.csv` bir mahallenin HANGİ İLÇEDE
  olduğunu bilen tek kaynaktır (modelin kategorileri düz bir isim listesidir,
  ilçe bilgisi taşımaz). Gruplama bu yüzden CSV'den gelir.
- Modelin kategorileri (`model["categories"]["neighborhood"]`) ise tahminin
  mahalle bazında yapılabildiği isimleri verir. Model tanımayan bir mahalle
  seçilirse tahmin sessizce ilçe geneline düşer; kullanıcıya seçtirdiğimiz
  ama karşılığını veremediğimiz bir alan bırakmamak için o isimler listeden
  çıkarılır.

Model hiç yüklü değilse (eğitilmemiş kurulum) filtre uygulanmaz: adil fiyat
zaten kapalıdır, ama ilan formu yine de çalışmalıdır.
"""

from __future__ import annotations

import pandas as pd

from app.config import MARKET_VALUES_CSV

# Yanıt sabittir; her istekte CSV okumamak için süreç başına bir kez kurulur.
# Anahtar: filtre uygulandı mı (model yüklü müydü).
_CACHE: dict[bool, list[dict]] = {}


def build_locations(known_neighborhoods: set[str] | None = None) -> list[dict]:
    """CSV'yi ilçelere göre gruplar; verilmişse modelin bilmediklerini eler.

    Dönüş: [{"district": "Kadıköy", "neighborhoods": ["Caferağa Mah.", ...]}]
    İlçeler ve mahalleler alfabetik sıralanır; mahallesi kalmayan ilçe düşer.
    """
    df = pd.read_csv(MARKET_VALUES_CSV)
    grouped: dict[str, set[str]] = {}
    for district, neighborhood in zip(df["district"], df["neighborhood"]):
        name = str(neighborhood).strip()
        if not name or (
            known_neighborhoods is not None and name not in known_neighborhoods
        ):
            continue
        grouped.setdefault(str(district).strip(), set()).add(name)
    return [
        {"district": district, "neighborhoods": sorted(names)}
        for district, names in sorted(grouped.items())
        if names
    ]


def model_neighborhoods() -> set[str] | None:
    """Yüklü modelin tanıdığı mahalle adları; model yoksa None."""
    from app.main import STATE  # döngüsel importu önler

    model = STATE.get("model")
    if model is None:
        return None
    return set(model["categories"]["neighborhood"])


def get_locations() -> list[dict]:
    """Uç noktanın döndürdüğü liste (süreç başına önbellekli)."""
    known = model_neighborhoods()
    filtered = known is not None
    if filtered not in _CACHE:
        _CACHE[filtered] = build_locations(known)
    return _CACHE[filtered]


def clear_cache() -> None:
    """Önbelleği boşaltır (testler ve model yeniden yüklenmesi için)."""
    _CACHE.clear()
