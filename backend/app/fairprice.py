"""Ev arkadaşlığı dinamiklerine göre adil oda payı hesabı.

Paylaşımlı evde kira nasıl bölüşülür?
- **Yatak odaları** kişiye özeldir: her odada bir kişi yaşar.
- **Salon, mutfak, banyo** ortaktır; kimseye ayrıca fatura edilmez, herkesin
  payına eşit dağılır.

Bu yüzden "2+1" bir dairede iki kişi yaşar ve kira ikiye bölünür — salon
(+1) kişi sayısına dahil edilmez. Model daire kirasının tamamını tahmin
ettiği için oda payı = tahmin / yatak odası sayısı.

Not: odalar eşit büyüklükte varsayılır; ilan verilerinde oda metrekaresi
yok. Fark varsa ilan sahibi kirayı elle ayarlar.
"""

import numpy as np
import pandas as pd

from app.indexing import DATA_PERIOD, is_configured, rent_index
from app.pricing import build_features

# Model tahmini için ilçe geneli varsayılanları (ilanlarda m²/yaş/kat yok)
DEFAULT_AREA = {1: 55.0, 2: 90.0, 3: 125.0, 4: 160.0}
DEFAULT_AGE = 15
DEFAULT_FLOOR = 3

# Adil bandın ±% kaçı "adil" sayılır (bandın dışına çıkınca uyarı)
SHARED_AREAS = ["Salon", "Mutfak", "Banyo"]


def parse_rooms(room_count: str | None) -> int:
    """'2+1' -> 2 yatak odası. Bilinmiyorsa 2 varsayılır."""
    if not room_count:
        return 2
    head = room_count.split("+")[0].strip()
    try:
        return max(1, int(head))
    except ValueError:
        return 2


def estimate_for_listing(district: str, room_count: str | None, asking_rent: int):
    """İlan için adil oda payı bandı ve kıyas sonucu döndürür.

    Model yüklü değilse None döner (çağıran 503 verir).
    """
    from app.main import STATE  # sunucu açılışında doldurulan model

    model = STATE.get("model")
    if model is None:
        return None

    rooms = parse_rooms(room_count)
    features = build_features(
        pd.DataFrame([{
            "room": rooms,
            "living room": 1,
            "area (m2)": DEFAULT_AREA.get(rooms, 90.0),
            "age": DEFAULT_AGE,
            "floor": DEFAULT_FLOOR,
            "district": district.strip(),
            # İlanlarda mahalle yok: tahmin ilçe geneline dayanır
            "neighborhood": "",
        }]),
        model["categories"],
    )

    factor, indexed_to = rent_index()
    band = sorted(
        float(np.exp(m.predict(features)[0])) * factor
        for m in model["models"].values()
    )
    flat_low, flat_mid, flat_high = band
    room_low, room_mid, room_high = (v / rooms for v in band)

    if asking_rent < room_low:
        verdict = "below"
    elif asking_rent > room_high:
        verdict = "above"
    else:
        verdict = "fair"

    return {
        "asking_price": asking_rent,
        "verdict": verdict,
        "deviation_pct": round((asking_rent - room_mid) / room_mid * 100, 1),
        # Oda payı (kullanıcının ödeyeceği)
        "room_low": round(room_low),
        "room_mid": round(room_mid),
        "room_high": round(room_high),
        # Dairenin tamamı (referans)
        "flat_low": round(flat_low),
        "flat_mid": round(flat_mid),
        "flat_high": round(flat_high),
        # Paylaşım açıklaması
        "bedrooms": rooms,
        "occupants": rooms,
        "shared_areas": SHARED_AREAS,
        "median_error_pct": round(model["served_medape"], 1),
        "data_period": DATA_PERIOD,
        "indexed_to": indexed_to,
        "indexed": is_configured(),
        "district_level": True,  # mahalle değil, ilçe geneline dayanıyor
    }
