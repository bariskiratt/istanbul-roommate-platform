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

from app import rent_model
from app.indexing import DATA_PERIOD, is_configured, rent_index

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


def resolve_neighborhood(model, neighborhood: str | None) -> str:
    """Modelin TANIDIĞI mahalle adını döndürür; tanımıyorsa boş dize.

    İlan mahallesi kullanıcıdan geldiği (ve eski ilanlarda hiç olmadığı) için
    modelin kategorilerinde bulunmayabilir. Bilinmeyen kategori pandas'ta NaN'a
    düşer, yani isteği patlatmaz — ama tahmin yine de ilçe geneline dayanır.
    Bunu burada açıkça yapıyoruz ki `district_level` bayrağı doğruyu söylesin.
    """
    if not neighborhood:
        return ""
    name = neighborhood.strip()
    return name if name in set(model["categories"]["neighborhood"]) else ""


def estimate_for_listing(
    district: str,
    room_count: str | None,
    asking_rent: int,
    neighborhood: str | None = None,
):
    """İlan için adil oda payı bandı ve kıyas sonucu döndürür.

    Mahalle verilmiş ve model onu tanıyorsa tahmin mahalle bazında yapılır;
    aksi hâlde ilçe geneline düşer (`district_level=True`).

    Model yüklü değilse None döner (çağıran 503 verir).
    """
    from app.main import STATE  # sunucu açılışında doldurulan model

    model = STATE.get("model")
    if model is None:
        return None

    rooms = parse_rooms(room_count)
    resolved = resolve_neighborhood(model, neighborhood)
    # Bant AWS Lambda'dan (tanımlıysa) ya da yerel modelden (app/rent_model.py).
    (band,), served_by = rent_model.bands(model, [{
        "room": rooms,
        "living_room": 1,
        "area": DEFAULT_AREA.get(rooms, 90.0),
        "age": DEFAULT_AGE,
        "floor": DEFAULT_FLOOR,
        "district": district,
        # Boş dize = mahalle bilinmiyor; model ilçe genelinden tahmin eder.
        "neighborhood": resolved,
    }])

    factor, indexed_to = rent_index()
    band = [v * factor for v in band]
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
        # Tahmin neye dayandı: mahalle kullanıldıysa False, ilçe geneli ise True.
        "district_level": resolved == "",
        # Kullanılan mahalle (yoksa/tanınmadıysa None) — arayüz "Kadıköy geneli"
        # ile "Caferağa Mah." arasındaki farkı dürüstçe yazabilsin diye.
        "neighborhood": resolved or None,
        # "lambda" ya da "local": bandı kim hesapladı (docs/AWS.md).
        "served_by": served_by,
    }
