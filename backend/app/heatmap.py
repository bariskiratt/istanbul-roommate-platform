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

        price = float(row.avg_price)
        exact[(district, neighborhood)] = price
        squashed[(district, squash(row.neighborhood))] = price

        if neighborhood in by_name and by_name[neighborhood] != price:
            ambiguous.add(neighborhood)
        by_name[neighborhood] = price

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

        price = exact.get((district, neighborhood))
        if price is None:
            price = squashed.get((district, squash(raw_neighborhood)))
        if price is None and not district:
            # İlçe bilgisi yok: yalnızca tekil mahalle adlarına güveniyoruz.
            price = by_name.get(neighborhood)

        props["id"] = index
        # Etiketlerde Türkçe karakterler korunur; eşleştirme normalize biçimle yapıldı.
        props["neighborhood"] = display_name(raw_neighborhood)
        props["district"] = display_name(raw_district)
        props["avg_price"] = price

        if price is not None:
            matched += 1

        # İstemciye gönderilmesi gerekmeyen ham Nominatim alanlarını at.
        for key in ("address", "place_id", "osm_type", "osm_id", "place_rank",
                    "category", "type", "importance", "display_name"):
            props.pop(key, None)

    return matched


def classify(avg_price, user_budget):
    """Tek bir mahallenin bütçeye göre durumunu döndürür."""
    if avg_price is None:
        return "nodata"
    if avg_price <= user_budget:
        return "safe"
    if avg_price <= user_budget * BORDERLINE_RATIO:
        return "borderline"
    return "expensive"


def build_budget_heatmap(feature_prices, user_budget):
    """Bütçeye göre kompakt bir durum listesi üretir.

    Geometriyi geri göndermek yerine (istek başına ~4 MB) yalnızca feature
    sırasına göre dizilmiş durum kodlarını döndürür (~10 KB). İstemci bu
    listeyi kendi tuttuğu geometriyle eşleştirip yeniden renklendirir.
    """
    statuses = [classify(price, user_budget) for price in feature_prices]
    counts = {key: 0 for key in STATUS_STYLES}
    for status in statuses:
        counts[status] += 1

    return {
        "budget": user_budget,
        "statuses": statuses,
        "summary": counts,
    }
