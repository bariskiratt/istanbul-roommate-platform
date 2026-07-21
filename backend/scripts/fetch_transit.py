"""İstanbul raylı sistem verisini OpenStreetMap'ten indirir.

Kaynak: Overpass API (OpenStreetMap). Üyelik/anahtar gerektirmez, lisans ODbL.
Alternatif resmi kaynak: https://data.ibb.gov.tr (GTFS) — daha eksiksiz ama
üyelik istiyor ve indirme elle yapılıyor.

Çalıştırma: python -m scripts.fetch_transit
Çıktı:      data/raw/transit_stations.json

İndirilenler:
* İstasyonlar (metro, Marmaray, tramvay, füniküler, banliyö) — ad + koordinat
* Hat ilişkileri (route relation) — hangi istasyonun hangi hatta olduğu

Hat bilgisi olmadan yalnızca "en yakın istasyon" hesaplanabilir; hatlar
olunca istasyonlar arası aktarmalı ulaşım grafiği kurulabiliyor.
"""

import json
import time

import requests

from app.config import RAW_DIR

OUTPUT = RAW_DIR / "transit_stations.json"

# Ücretsiz aynalar sık sık meşgul döner; sırayla denenir.
MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# İstanbul'u kapsayan kutu. `area[name=İstanbul]` sorgusu daha zarif ama
# alan araması pahalı olduğu için sunucular sık sık zaman aşımına düşürüyor.
BBOX = "40.75,28.40,41.40,29.60"

# Şehir içi raylı sistemler. `network` filtresi olmadan Ankara/Konya YHT
# hatları da geliyor; onlar bu proje için anlamsız.
#
# Önemli: OSM'de hat ilişkileri `railway=station` düğümlerini DEĞİL,
# `public_transport=stop_position` düğümlerini üye alır. Bu yüzden
# istasyonları ayrı sorgulamak yerine ilişkilerin üyelerinden (`node(r)`)
# türetiyoruz — böylece istasyon <-> hat bağı garanti tutuyor.
NETWORK_RE = "İstanbul|Marmaray|Metro|Tramvay"

TRANSIT_QUERY = f"""
[out:json][timeout:240][bbox:{BBOX}];
relation["type"="route"]["route"~"^(subway|light_rail|train|tram|funicular)$"]
        ["network"~"{NETWORK_RE}",i]->.routes;
.routes out body;
node(r.routes);
out body;
"""

MAX_ATTEMPTS = 4


def overpass(query, label):
    """Sorguyu aynalar arasında dolaşarak, artan beklemeyle dener.

    `requests` kullanıyoruz çünkü kendi kök sertifikalarını (certifi) getiriyor;
    python.org kurulumlarında sistem sertifikaları eksik olabiliyor ve düz
    urllib "CERTIFICATE_VERIFY_FAILED" ile düşüyor.
    """
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        mirror = MIRRORS[(attempt - 1) % len(MIRRORS)]
        host = mirror.split("/")[2]
        print(f"   [{label}] deneme {attempt}/{MAX_ATTEMPTS} → {host}")
        try:
            response = requests.post(
                mirror,
                data={"data": query},
                headers={"User-Agent": "istanbul-real-estate-heatmap/1.0"},
                timeout=240,
            )
            response.raise_for_status()

            # Meşgul sunucu 200 ile HTML hata sayfası dönebiliyor.
            if not response.text.lstrip().startswith("{"):
                raise ValueError("JSON yerine hata sayfası döndü (sunucu meşgul)")

            data = response.json()
            print(f"   [{label}] ✅ {len(data.get('elements', []))} kayıt")
            return data

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            print(f"   [{label}] ⚠️  {str(exc)[:110]}")
            if attempt < MAX_ATTEMPTS:
                wait = 5 * attempt
                print(f"   [{label}] {wait} sn bekleniyor...")
                time.sleep(wait)

    raise RuntimeError(f"{label} indirilemedi: {last_error}")


def merge_duplicate_stops(stops, radius_deg=0.006):
    """Aynı istasyonun yön başına ayrı düğümlerini tek kayda indirir.

    OSM'de her hat yönü kendi `stop_position` düğümünü taşır; ham veride
    "Üsküdar" 3 ayrı kayıt olarak, her biri tek bir hatla görünür. Böyle
    bırakılırsa aktarma noktaları kaybolur ve ulaşım grafiği kopuk çıkar.

    Aynı ada sahip ve birbirine ~500 m'den yakın düğümler birleştirilir;
    hat listeleri birleşiminin alınmasıyla gerçek aktarma yapısı ortaya çıkar.
    Mesafe şartı, farklı semtlerdeki aynı adlı durakların (örn. "Merkez")
    yanlışlıkla kaynaşmasını engelliyor.

    (birleşmiş_istasyonlar, {eski_düğüm_id: yeni_indeks}) döndürür. Eşleme
    şart: hat sıralamaları hâlâ eski düğüm kimliklerine bakıyor ve ulaşım
    grafiği "hangi istasyon hangisinden sonra geliyor" bilgisine dayanıyor.
    """
    by_name = {}
    for stop in stops:
        by_name.setdefault(stop["name"], []).append(stop)

    merged, id_map = [], {}
    for name, group in by_name.items():
        clusters = []
        for stop in group:
            for cluster in clusters:
                head = cluster[0]
                if (abs(head["lat"] - stop["lat"]) < radius_deg
                        and abs(head["lon"] - stop["lon"]) < radius_deg):
                    cluster.append(stop)
                    break
            else:
                clusters.append([stop])

        for cluster in clusters:
            index = len(merged)
            merged.append({
                "name": name,
                "lat": sum(s["lat"] for s in cluster) / len(cluster),
                "lon": sum(s["lon"] for s in cluster) / len(cluster),
                "lines": sorted({ref for stop in cluster for ref in stop["lines"]}),
            })
            for stop in cluster:
                id_map[stop["id"]] = index

    return merged, id_map


RAW_CACHE = RAW_DIR / "transit_overpass_raw.json"


def main():
    print("🚇 İstanbul raylı sistem verisi indiriliyor (OpenStreetMap)...")

    # Ağ ve işlemeyi ayır: ham Overpass yanıtını önbelleğe al. Böylece
    # sonraki çalıştırmalar (ve grafik geliştirmesi) meşgul aynaları
    # tekrar yormadan yerel dosyayı kullanır. Yeniden indirmek için
    # data/raw/transit_overpass_raw.json dosyasını sil.
    if RAW_CACHE.exists():
        print(f"   📁 Önbellek kullanılıyor: {RAW_CACHE.name} "
              f"(yeniden indirmek için sil)")
        raw = json.loads(RAW_CACHE.read_text(encoding="utf-8"))
    else:
        raw = overpass(TRANSIT_QUERY, "hatlar+duraklar")
        RAW_CACHE.write_text(json.dumps(raw), encoding="utf-8")

    elements = raw.get("elements", [])

    stations = {}
    for element in elements:
        if element.get("type") != "node" or "lat" not in element:
            continue
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue
        stations[element["id"]] = {
            "id": element["id"],
            "name": name,
            "lat": element["lat"],
            "lon": element["lon"],
            "lines": [],
        }

    lines = []
    for element in elements:
        if element.get("type") != "relation":
            continue
        tags = element.get("tags", {})
        ref = tags.get("ref") or tags.get("name", "")
        if not ref:
            continue

        members = [
            m["ref"] for m in element.get("members", [])
            if m.get("type") == "node" and m["ref"] in stations
        ]
        if not members:
            continue

        lines.append({
            "ref": ref,
            "name": tags.get("name", ""),
            "route": tags.get("route", ""),
            "stations": members,
        })
        for node_id in members:
            if ref not in stations[node_id]["lines"]:
                stations[node_id]["lines"].append(ref)

    # Hiçbir hatta bağlı olmayan istasyonlar grafikte işe yaramaz.
    connected = {k: v for k, v in stations.items() if v["lines"]}
    merged, id_map = merge_duplicate_stops(connected.values())

    # Hat sıralamalarını birleşmiş istasyon indekslerine çevir. Ardışık
    # yinelemeler (aynı istasyonun iki durak düğümü peş peşe) atılır,
    # yoksa grafikte sıfır uzunlukta kenarlar oluşur.
    for line in lines:
        sequence = []
        for node_id in line["stations"]:
            index = id_map.get(node_id)
            if index is not None and (not sequence or sequence[-1] != index):
                sequence.append(index)
        line["stations"] = sequence
    lines = [line for line in lines if len(line["stations"]) >= 2]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "source": "OpenStreetMap via Overpass API (ODbL)",
                "stations": merged,
                "lines": lines,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )

    refs = sorted({line["ref"] for line in lines})
    interchanges = [s for s in merged if len(s["lines"]) > 1]
    if len(merged) < 150:
        print(f"\n⚠️  Yalnızca {len(merged)} istasyon bulundu — beklenen 200+. "
              f"Overpass eksik yanıt vermiş olabilir, betiği tekrar çalıştır.")
    print(f"\n💾 '{OUTPUT.relative_to(OUTPUT.parent.parent.parent)}' yazıldı.")
    print(f"   {len(merged)} istasyon ({len(interchanges)} aktarma noktası), "
          f"{len(lines)} hat yönü, {len(refs)} benzersiz hat")
    print(f"   Hatlar: {', '.join(refs[:25])}{' ...' if len(refs) > 25 else ''}")


if __name__ == "__main__":
    main()
