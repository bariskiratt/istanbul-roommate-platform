"""Alternatif semt önerisi (app.transit) ve ilçe etiketi tamamlama.

Özellik arayüzde kapalıydı (docs/ALGORITHMS.md §2.6). Bu dosya, onu
kapattıran sorunların geri gelmemesi için var:

* sıralama yürüme mesafesini görmüyordu (1.19 km yürüme ile 0.05 km aynı);
* "8 durak" denen şey 3 durak + 1 aktarmanın ağ maliyetiydi;
* hedeften PAHALI mahalleler "alternatif" diye önerilebiliyordu (eksi tasarruf);
* öğrenci bütçesinde liste sessizce boş dönüyordu;
* ilçesi olmayan 372 poligon "Rumeli Hisarı, " gibi boş etiketle çıkıyordu;
* OSM'deki yapımı süren "Üsküdar-Cevizli" tramvayı gerçek hat sayılıyordu.
"""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import transit
from app.config import MARKET_VALUES_CSV, NEIGHBORHOOD_GEOJSON
from app.heatmap import annotate_features
from app.main import STATE, app
from app.transit import TRANSIT_PATH, AccessibilityIndex, TransitNetwork

# Hat boyunca istasyonlar ~2.5 km arayla (41° enlemde 0.03° boylam), böylece
# her mahalle yalnızca kendi istasyonunun yürüme mesafesinde kalır.
#
#   A ── B ── C ── D        M1 (doğu-batı)
#             │
#             E             M2 (C'den kuzeye)
#             │
#             F
#   X                       kodsuz "Üsküdar-Cevizli" hattı (A'nın güneyi)
#   └─ Y
STATIONS = [
    {"name": "A", "lat": 41.000, "lon": 29.00},  # 0
    {"name": "B", "lat": 41.000, "lon": 29.03},  # 1
    {"name": "C", "lat": 41.000, "lon": 29.06},  # 2
    {"name": "D", "lat": 41.000, "lon": 29.09},  # 3
    {"name": "E", "lat": 41.025, "lon": 29.06},  # 4
    {"name": "F", "lat": 41.050, "lon": 29.06},  # 5
    {"name": "X", "lat": 40.975, "lon": 29.00},  # 6
    {"name": "Y", "lat": 40.950, "lon": 29.00},  # 7
]
LINES = [
    {"ref": "M1", "stations": [0, 1, 2, 3]},
    {"ref": "M2", "stations": [2, 4, 5]},
    {"ref": "Üsküdar-Cevizli", "stations": [6, 7]},
]


def square(lat, lon, half=0.001):
    ring = [
        [lon - half, lat - half], [lon + half, lat - half],
        [lon + half, lat + half], [lon - half, lat + half],
        [lon - half, lat - half],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


# (id, ad, ilçe, enlem, boylam, fiyat, ilan sayısı)
PLACES = [
    (0, "Hedef", "Merkez", 41.000, 29.00, 100_000, 40),   # A'nın üstünde
    (1, "Yakın", "Doğu", 41.002, 29.03, 30_000, 20),      # B'ye ~0.2 km
    (2, "Uzak", "Doğu", 41.009, 29.03, 25_000, 20),       # B'ye ~1.0 km
    (3, "Kuzey", "Kuzey", 41.025, 29.06, 20_000, 3),      # E, aktarmalı
    (4, "Pahalı", "Doğu", 41.000, 29.09, 150_000, 20),    # D, hedeften pahalı
    (5, "Sınır", "Doğu", 41.000, 29.06, 40_000, 20),      # C
    (6, "Tramvay", "Güney", 40.970, 29.00, 10_000, 20),   # yalnız X'e yakın
    (7, "Verisiz", "Doğu", 41.001, 29.06, None, None),    # C, fiyatı yok
]


@pytest.fixture()
def index():
    features = [
        {
            "type": "Feature",
            "properties": {
                "id": pid, "neighborhood": name, "district": district,
                "avg_price": price, "listing_count": count,
            },
            "geometry": square(lat, lon),
        }
        for pid, name, district, lat, lon, price, count in PLACES
    ]
    prices = {pid: price for pid, *_rest, price, _count in PLACES}
    return AccessibilityIndex(TransitNetwork(STATIONS, LINES), features, prices)


def names(items):
    return [item["name"] for item in items]


def test_easy_reach_counts_stops_and_transfers_separately():
    network = TransitNetwork(STATIONS, LINES)
    reach = network.easy_reach(0)
    assert reach[0] == (0, 0, 0)
    assert reach[2] == (2, 2, 0)
    # A -> C iki durak, C'de M2'ye aktarma, bir durak daha: maliyet 2+1+5.
    assert reach[4] == (8, 3, 1)
    assert reach[5] == (9, 4, 1)


def test_uncoded_line_is_not_part_of_the_network(index):
    network = index.network
    assert [line["ref"] for line in network.lines] == ["M1", "M2"]
    assert 6 not in network.served and 7 not in network.served
    result = index.recommend(6, 50_000)
    assert result["reachable"] is False
    assert result["reason"] == "not_near_rail"


def test_ranking_counts_walking_and_hides_pricier_places(index):
    result = index.recommend(0, 30_000)
    assert result["reachable"] is True
    recs = result["recommendations"]
    # "Uzak" Kuzey'den bir durak yakın ama istasyona 1 km yürüme istiyor;
    # aktarmalı Kuzey ondan önce gelir. Pahalı (hedeften pahalı), Sınır
    # (bütçenin %20'sinden fazla üstünde) ve Verisiz hiç önerilmez.
    assert names(recs) == ["Yakın", "Kuzey", "Uzak"]
    yakin, kuzey, uzak = recs
    assert (yakin["stops"], yakin["transfers"]) == (1, 0)
    assert (kuzey["stops"], kuzey["transfers"]) == (3, 1)
    assert yakin["minutes"] < kuzey["minutes"] < uzak["minutes"]
    assert uzak["walk_minutes"] == 15
    assert all(rec["saving"] > 0 for rec in recs)
    assert all(rec["status"] == "safe" for rec in recs)
    assert result["cheapest"] == []


def test_borderline_places_are_included_and_marked(index):
    recs = index.recommend(0, 35_000)["recommendations"]
    status = {rec["name"]: rec["status"] for rec in recs}
    assert status["Sınır"] == "borderline"  # 40.000 <= 35.000 * 1.2
    assert "Pahalı" not in status


def test_no_fit_returns_cheapest_nearby_with_the_gap(index):
    result = index.recommend(0, 15_000)
    assert result["recommendations"] == []
    cheapest = result["cheapest"]
    assert names(cheapest) == ["Kuzey", "Uzak", "Yakın"]
    assert cheapest[0]["over_budget"] == 5_000


def test_cheapest_target_nearby_gets_nothing(index):
    # Kuzey (20.000) yakınında ondan ucuz mahalle yok.
    result = index.recommend(3, 10_000)
    assert result["reachable"] is True
    assert result["recommendations"] == []
    assert result["cheapest"] == []


def test_low_confidence_is_flagged(index):
    recs = index.recommend(0, 30_000)["recommendations"]
    assert {rec["name"]: rec["low_confidence"] for rec in recs} == {
        "Yakın": False, "Kuzey": True, "Uzak": False,
    }


def test_max_minutes_caps_the_reach(index, monkeypatch):
    monkeypatch.setattr(transit, "MAX_MINUTES", 10)
    result = index.recommend(0, 30_000)
    assert names(result["recommendations"]) == ["Yakın"]
    assert result["max_minutes"] == 10


def test_place_between_two_lines_uses_the_shorter_one():
    # Mahalle A'ya ~1.06 km, Z'ye ~0.33 km. Z ayrı bir hatta (M9, C'ye
    # bağlı) ve hedef yalnızca A'ya yakın. Mahalle yalnızca en yakın
    # istasyonuna (Z) bağlansaydı hedeften ona A -> C -> aktarma -> Z
    # yoluyla gidilirdi; iki istasyona da bağlı olduğu için A'dan yürünür.
    stations = STATIONS[:4] + [{"name": "Z", "lat": 41.0125, "lon": 29.00}]
    lines = [{"ref": "M1", "stations": [0, 1, 2, 3]},
             {"ref": "M9", "stations": [4, 2]}]
    features = [
        {"properties": {"id": 0, "neighborhood": "Hedef", "district": "M",
                        "avg_price": 100_000, "listing_count": 40},
         "geometry": square(41.000, 29.00)},
        {"properties": {"id": 1, "neighborhood": "Arada", "district": "M",
                        "avg_price": 20_000, "listing_count": 40},
         "geometry": square(41.0095, 29.00)},
    ]
    index = AccessibilityIndex(
        TransitNetwork(stations, lines), features, {0: 100_000, 1: 20_000}
    )
    (rec,) = index.recommend(0, 30_000)["recommendations"]
    assert (rec["stops"], rec["transfers"]) == (0, 0)


def test_alternatives_endpoint(index, monkeypatch):
    client = TestClient(app)
    monkeypatch.setitem(STATE, "access", index)
    res = client.get("/api/alternatives", params={"neighborhood_id": 0, "budget": 30_000})
    assert res.status_code == 200
    assert names(res.json()["recommendations"]) == ["Yakın", "Kuzey", "Uzak"]
    assert client.get(
        "/api/alternatives", params={"neighborhood_id": 999, "budget": 30_000}
    ).status_code == 404

    monkeypatch.delitem(STATE, "access")
    assert client.get(
        "/api/alternatives", params={"neighborhood_id": 0, "budget": 30_000}
    ).status_code == 503


def test_district_is_filled_from_the_matched_price_row():
    df = pd.DataFrame({
        "district": ["Beşiktaş", "Sarıyer", "Kadıköy", "Sarıyer"],
        "neighborhood": ["Bebek Mah.", "Rumeli Hisarı Mah.", "Merkez Mah.", "Merkez Mah."],
        "total_listings": [40, 6, 10, 12],
        "avg_price": [115_000.0, 55_000.0, 30_000.0, 35_000.0],
        "avg_price_per_m2": [0, 0, 0, 0],
    })
    geojson = {"features": [
        {"properties": {"address": {"suburb": "Bebek Mahallesi", "town": "Beşiktaş"}}},
        {"properties": {"address": {"suburb": "Rumeli Hisarı Mahallesi"}}},
        {"properties": {"address": {"suburb": "Merkez Mahallesi"}}},
    ]}
    assert annotate_features(geojson, df) == 2
    props = [f["properties"] for f in geojson["features"]]
    assert (props[0]["district"], props[0]["avg_price"]) == ("Beşiktaş", 115_000.0)
    # İlçesiz poligon, ad tek bir ilçede geçtiği için o satırın ilçesini alır.
    assert (props[1]["district"], props[1]["avg_price"]) == ("Sarıyer", 55_000.0)
    # Ad iki ilçede geçiyor: ne fiyat ne ilçe tahmin edilir.
    assert (props[2]["district"], props[2]["avg_price"]) == ("", None)


@pytest.mark.skipif(not TRANSIT_PATH.exists(), reason="toplu taşıma verisi yok")
def test_committed_data_produces_shippable_rows():
    """Kayıtlı veriyle her hedef için: boş ilçe yok, hedeften pahalı öneri
    yok, bütçeyi %20'den fazla aşan öneri yok, süre sınırı aşılmıyor."""
    geojson = json.loads(NEIGHBORHOOD_GEOJSON.read_text(encoding="utf-8"))
    annotate_features(geojson, pd.read_csv(MARKET_VALUES_CSV))
    features = geojson["features"]
    prices = {f["properties"]["id"]: f["properties"]["avg_price"] for f in features}
    index = AccessibilityIndex(TransitNetwork.load(), features, prices)

    assert all(line["ref"] != "Üsküdar-Cevizli" for line in index.network.lines)
    targets = [p for p in index.places.values() if p["price"] and p["stations"]]
    assert len(targets) > 250
    for target in targets:
        for budget in (15_000, 25_000):
            result = index.recommend(target["id"], budget)
            assert result["reachable"] is True
            for rec in result["recommendations"] + result["cheapest"]:
                assert rec["district"], rec
                assert rec["price"] < target["price"]
                assert rec["minutes"] <= transit.MAX_MINUTES
            for rec in result["recommendations"]:
                assert rec["price"] <= budget * 1.2
