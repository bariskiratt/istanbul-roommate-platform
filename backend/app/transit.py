"""Toplu taşıma erişilebilirliği ve alternatif semt önerisi (Modül 3).

Fikir: kullanıcı pahalı bir semtte (örn. Beşiktaş) ev arıyorsa ama bütçesi
yetmiyorsa, sistem hedefe **raylı sistemle** kolay ulaşılan, bütçeye uygun
alternatif mahalleleri önerir.

Neden düz mesafe değil: İstanbul'da kuş uçuşu yakınlık yanıltıcıdır. Boğaz'ın
iki yakası kuş uçuşu 1-2 km'dir ama arada köprü/Marmaray yoksa ulaşım yarım
saati bulur. Bu yüzden mesafe değil, raylı sistem ağı üzerinde **aktarmalı
istasyon sayısı** temel alınır.
"""

import json
import math
from collections import deque

from app.config import RAW_DIR

TRANSIT_PATH = RAW_DIR / "transit_stations.json"

# Bir mahallenin merkezi bir istasyona bu mesafeden yakınsa "raylı sisteme
# yürüme mesafesinde" sayılır (km). ~1.2 km, rahat bir yürüyüş üst sınırı.
WALK_KM = 1.2

# Ağ üzerinde iki istasyon arası "yakınlık" eşiği. Aktarma dahil bu kadar
# duraktan uzaktaki istasyonlar "kolay ulaşılır" sayılmaz.
MAX_HOPS = 12

# Aktarma, aynı hatta bir durak ilerlemekten daha maliyetli (bekleme + yürüme).
# Durak = 1 birim, aktarma = TRANSFER_COST birim.
TRANSFER_COST = 5


def haversine_km(lat1, lon1, lat2, lon2):
    """İki koordinat arası büyük daire mesafesi (km)."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(a))


def polygon_centroid(geometry):
    """GeoJSON Polygon/MultiPolygon için ağırlıklı alan merkezini döndürür.

    Basit nokta ortalaması, sık köşeli kenarlara doğru kayar; kabuk
    (shoelace) formülüyle gerçek alan merkezi hesaplanıyor. Dejenere
    (sıfır alan) halkalarda köşe ortalamasına düşülür.
    """
    if geometry["type"] == "Polygon":
        rings = [geometry["coordinates"][0]]
    elif geometry["type"] == "MultiPolygon":
        rings = [poly[0] for poly in geometry["coordinates"]]
    else:
        return None

    total_area = cx = cy = 0.0
    for ring in rings:
        area = 0.0
        rx = ry = 0.0
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            cross = x0 * y1 - x1 * y0
            area += cross
            rx += (x0 + x1) * cross
            ry += (y0 + y1) * cross
        area *= 0.5
        if area:
            rx /= (6 * area)
            ry /= (6 * area)
            total_area += area
            cx += rx * area
            cy += ry * area

    if total_area:
        return cy / total_area, cx / total_area  # (lat, lon)

    # Alan yoksa köşe ortalamasına düş.
    pts = [p for ring in rings for p in ring]
    return (sum(p[1] for p in pts) / len(pts),
            sum(p[0] for p in pts) / len(pts))


class TransitNetwork:
    """Raylı sistem ağı ve mahalle-erişilebilirlik hesapları.

    Ağı bir kez kurar (istasyonlar + hatlar -> komşuluk grafiği), sonra her
    mahalle için en yakın istasyonu ve o istasyondan ağ üzerinde kolay
    ulaşılan istasyon kümesini önbelleğe alır.
    """

    def __init__(self, stations, lines):
        self.stations = stations
        self.lines = lines
        self._adjacency = self._build_adjacency()

    @classmethod
    def load(cls, path=TRANSIT_PATH):
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["stations"], data["lines"])

    def _build_adjacency(self):
        """Kenarları hat bilgisiyle sakla: {i: {j: {hat_ref, ...}}}.

        Kenarın hangi hat(lar)dan oluştuğunu kenarda tutmak, aktarma cezasını
        doğru uygulamanın tek yolu: iki istasyon "aynı hatta üye" olabilir
        ama o hatta ardışık olmayabilir. Yalnızca hat sırasında yan yana
        gelen çiftler kenar oluşturur.
        """
        adjacency = {i: {} for i in range(len(self.stations))}
        for line in self.lines:
            ref = line["ref"]
            sequence = line["stations"]
            for a, b in zip(sequence, sequence[1:]):
                adjacency[a].setdefault(b, set()).add(ref)
                adjacency[b].setdefault(a, set()).add(ref)
        return adjacency

    def easy_reach(self, source, max_hops=MAX_HOPS):
        """Kaynak istasyondan kolay ulaşılan istasyonların {indeks: maliyet}.

        Her istasyona hangi hatla ulaşıldığını takip eden Dijkstra: bir kenarı
        geçmek 1 birim, ama gelinen hattan farklı bir hatta binmek ek olarak
        TRANSFER_COST öder. Böylece "3 durak ötede ama 2 aktarmalı" bir yer,
        "5 durak ötede ama aktarmasız" bir yerden pahalı çıkar.
        """
        # Durum: (istasyon, o istasyona giriş hattı). Aynı istasyona farklı
        # hatla ulaşmak farklı devam maliyetleri doğurduğu için hat durumun
        # parçası olmalı.
        best = {(source, None): 0}
        frontier = [(0, source, None)]
        result = {}

        while frontier:
            frontier.sort()
            cost, node, via_line = frontier.pop(0)
            if best.get((node, via_line), 1e9) < cost:
                continue

            if node != source:
                result[node] = min(result.get(node, 1e9), cost)
            if cost >= max_hops:
                continue

            for neighbor, refs in self._adjacency[node].items():
                for ref in refs:
                    step = 1 + (TRANSFER_COST if via_line and ref != via_line else 0)
                    new_cost = cost + step
                    if new_cost > max_hops:
                        continue
                    state = (neighbor, ref)
                    if new_cost < best.get(state, 1e9):
                        best[state] = new_cost
                        frontier.append((new_cost, neighbor, ref))

        return result

    def nearest_station(self, lat, lon):
        """(istasyon_indeksi, km) — noktaya en yakın istasyon."""
        best_index, best_km = None, 1e9
        for index, station in enumerate(self.stations):
            km = haversine_km(lat, lon, station["lat"], station["lon"])
            if km < best_km:
                best_index, best_km = index, km
        return best_index, best_km


class AccessibilityIndex:
    """Mahalleleri raylı sistem ağına bağlar ve alternatif semt önerir.

    Kurulum (sunucu açılışında bir kez):
    * her mahallenin merkezini hesapla
    * merkeze en yakın istasyonu bul (yürüme mesafesindeyse)
    * her istasyonun kolay-ulaşılır komşu istasyonlarını önceden hesapla
    """

    def __init__(self, network, features, market_prices):
        self.network = network
        # {mahalle_id: {"name","district","lat","lon","station","walk_km","price"}}
        self.places = {}
        # istasyon indeksi -> o istasyona bağlı mahalle id'leri
        self._by_station = {}
        self._reach_cache = {}

        for feature in features:
            props = feature["properties"]
            centroid = polygon_centroid(feature["geometry"])
            if centroid is None:
                continue
            lat, lon = centroid
            station_index, walk_km = network.nearest_station(lat, lon)

            place = {
                "id": props["id"],
                "name": props.get("neighborhood", ""),
                "district": props.get("district", ""),
                "lat": lat,
                "lon": lon,
                "station": station_index,
                "walk_km": round(walk_km, 2),
                "price": market_prices.get(props["id"]),
            }
            self.places[props["id"]] = place
            if walk_km <= WALK_KM:
                self._by_station.setdefault(station_index, []).append(props["id"])

    def _reachable_places(self, station_index):
        """İstasyondan kolay ulaşılan (yürüme mesafesindeki) mahalleler.

        {mahalle_id: maliyet}. Kaynağın kendi istasyonundaki mahalleler
        maliyet 0 ile dahil.
        """
        if station_index in self._reach_cache:
            return self._reach_cache[station_index]

        reach = {station_index: 0}
        reach.update(self.network.easy_reach(station_index))

        places = {}
        for target_station, cost in reach.items():
            for place_id in self._by_station.get(target_station, []):
                places[place_id] = min(places.get(place_id, 1e9), cost)

        self._reach_cache[station_index] = places
        return places

    def recommend(self, target_id, budget, limit=6):
        """Hedef mahalleye raylı sistemle yakın, bütçeye uygun alternatifler.

        Dönen her öğe: mahalle bilgisi + hedefe ağ maliyeti + tasarruf.
        Hedefin kendisi ve bütçeyi aşan mahalleler elenir; sonuç önce
        ulaşım kolaylığına, sonra ucuzluğa göre sıralanır.
        """
        target = self.places.get(target_id)
        if target is None:
            return {"error": "Mahalle bulunamadı."}
        if target["walk_km"] > WALK_KM:
            return {
                "target": _public(target),
                "reachable": False,
                "message": "Bu mahalle raylı sisteme yürüme mesafesinde değil; "
                           "ulaşım tabanlı öneri üretilemiyor.",
                "recommendations": [],
            }

        reachable = self._reachable_places(target["station"])
        target_price = target["price"]

        candidates = []
        for place_id, cost in reachable.items():
            if place_id == target_id:
                continue
            place = self.places[place_id]
            price = place["price"]
            if price is None or price > budget:
                continue

            saving = (target_price - price) if target_price else None
            candidates.append({
                **_public(place),
                "network_cost": round(cost, 1),
                "saving": round(saving) if saving is not None else None,
            })

        # Önce en kolay ulaşım (düşük maliyet), eşitlikte en ucuz.
        candidates.sort(key=lambda c: (c["network_cost"], c["price"] or 1e12))

        return {
            "target": _public(target),
            "reachable": True,
            "budget": budget,
            "recommendations": candidates[:limit],
        }


def _public(place):
    """Mahalle kaydından istemciye gidecek alanları seçer."""
    return {
        "id": place["id"],
        "name": place["name"],
        "district": place["district"],
        "price": place["price"],
        "walk_km": place["walk_km"],
        "lat": round(place["lat"], 5),
        "lon": round(place["lon"], 5),
    }
