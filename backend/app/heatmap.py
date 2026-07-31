"""Bütçe ısı haritası: fiyat indeksi kurulumu ve renklendirme.

Tasarım notu (performans): mahalle fiyatları bütçeye bağlı değildir, bu yüzden
GeoJSON <-> CSV eşleştirmesi sunucu açılırken BİR KEZ yapılır. Her istekte
yalnızca "fiyat -> renk" karşılaştırması çalışır; bu O(mahalle) ve saniyenin
binde biri kadar sürer.
"""

from app.normalize import (
    display_name,
    extract_place,
    norm_district,
    norm_neighborhood,
    squash,
)

# Bütçenin bu oranına kadar olan bölgeler "sınırda" sayılır.
BORDERLINE_RATIO = 1.20

# Bu sayının altında ilanı olan mahallenin medyanı zayıf temsil eder (örn.
# Kazlıçeşme: 6 lüks ilan medyanı 137.500 ₺'ye taşıyor). Renk yine verilir —
# harita boş kalmasın — ama "düşük güven" olarak işaretlenir; istemci bu
# mahalleleri soluk/kesik çizgiyle çizip uyarı gösterir.
MIN_LISTINGS = 8

STATUS_STYLES = {
    "safe": {"label": "Bütçene Uygun", "color": "#2ecc71"},
    "borderline": {"label": "Sınırda", "color": "#f1c40f"},
    "expensive": {"label": "Bütçeni Aşıyor", "color": "#e74c3c"},
    "nodata": {"label": "Veri Yok", "color": "#95a5a6"},
}


def build_price_index(df):
    """CSV'den kademeli eşleştirme için üç sözlük üretir.

    1. exact     -> (ilçe, mahalle) tam eşleşme
    2. squashed  -> (ilçe, boşluksuz mahalle); yazım farklarını tolere eder
    3. by_name   -> yalnızca mahalle adı; GeoJSON'da ilçe yoksa son çare

    by_name'de aynı ad birden fazla ilçede geçiyorsa hangi fiyatın doğru
    olduğu belirsizdir, o ad indeksten çıkarılır.
    """
    exact, squashed, by_name, ambiguous = {}, {}, {}, set()

    for row in df.itertuples(index=False):
        district = norm_district(row.district)
        neighborhood = norm_neighborhood(row.neighborhood)
        if not neighborhood:
            continue

        # (fiyat, ilan sayısı) — sayı, medyanın güvenilirliğini işaretlemek için
        entry = (float(row.avg_price), int(row.total_listings))
        exact[(district, neighborhood)] = entry
        squashed[(district, squash(row.neighborhood))] = entry

        if neighborhood in by_name and by_name[neighborhood] != entry:
            ambiguous.add(neighborhood)
        by_name[neighborhood] = entry

    for name in ambiguous:
        by_name.pop(name, None)

    return exact, squashed, by_name


def annotate_features(geojson_data, df):
    """Her feature'a kalıcı alanları (id, ad, fiyat) yazar. Sunucu açılışında
    bir kez çağrılır. Eşleşen mahalle sayısını döndürür."""
    exact, squashed, by_name = build_price_index(df)
    matched = 0

    for index, feature in enumerate(geojson_data.get("features", [])):
        props = feature.setdefault("properties", {})
        raw_neighborhood, raw_district = extract_place(props.get("address"))
        neighborhood = norm_neighborhood(raw_neighborhood)
        district = norm_district(raw_district)

        entry = exact.get((district, neighborhood))
        if entry is None:
            entry = squashed.get((district, squash(raw_neighborhood)))
        if entry is None and not district:
            # İlçe bilgisi yok: yalnızca tekil mahalle adlarına güveniyoruz.
            entry = by_name.get(neighborhood)

        price, listing_count = entry if entry is not None else (None, None)

        props["id"] = index
        # Etiketlerde Türkçe karakterler korunur; eşleştirme normalize biçimle yapıldı.
        props["neighborhood"] = display_name(raw_neighborhood)
        props["district"] = display_name(raw_district)
        props["avg_price"] = price
        props["listing_count"] = listing_count

        if price is not None:
            matched += 1

        # İstemciye gönderilmesi gerekmeyen ham Nominatim alanlarını at.
        for key in ("address", "place_id", "osm_type", "osm_id", "place_rank",
                    "category", "type", "importance", "display_name"):
            props.pop(key, None)

    return matched


def classify(avg_price, user_budget, listing_count=None):
    """Tek bir mahallenin bütçeye göre durumunu döndürür.

    listing_count yalnızca güven işaretlemesinde kullanılır; az ilanlı
    mahalle de renklendirilir (bkz. build_budget_heatmap -> low_confidence).
    """
    if avg_price is None:
        return "nodata"
    if avg_price <= user_budget:
        return "safe"
    if avg_price <= user_budget * BORDERLINE_RATIO:
        return "borderline"
    return "expensive"


def build_budget_heatmap(feature_prices, user_budget, feature_counts=None):
    """Bütçeye göre kompakt bir durum listesi üretir.

    Geometriyi geri göndermek yerine (istek başına ~4 MB) yalnızca feature
    sırasına göre dizilmiş durum kodlarını döndürür (~10 KB). İstemci bu
    listeyi kendi tuttuğu geometriyle eşleştirip yeniden renklendirir.

    `low_confidence`: aynı sırada, o mahallenin medyanının az ilana dayanıp
    dayanmadığı. Renk yine verilir; istemci bunları soluk çizer.
    """
    if feature_counts is None:
        feature_counts = [None] * len(feature_prices)
    statuses = [classify(price, user_budget) for price in feature_prices]
    low_confidence = [
        price is not None and count is not None and count < MIN_LISTINGS
        for price, count in zip(feature_prices, feature_counts)
    ]
    counts = {key: 0 for key in STATUS_STYLES}
    for status in statuses:
        counts[status] += 1

    return {
        "budget": user_budget,
        "statuses": statuses,
        "low_confidence": low_confidence,
        "summary": counts | {"low_confidence": sum(low_confidence)},
    }
