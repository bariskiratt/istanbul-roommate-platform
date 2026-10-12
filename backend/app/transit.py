"""Toplu taşıma erişilebilirliği ve alternatif semt önerisi (Modül 3).

Fikir: kullanıcı pahalı bir semtte (örn. Beşiktaş) ev arıyorsa ama bütçesi
yetmiyorsa, sistem hedefe **raylı sistemle** kolay ulaşılan, bütçeye uygun
alternatif mahalleleri önerir.

Neden düz mesafe değil: İstanbul'da kuş uçuşu yakınlık yanıltıcıdır. Boğaz'ın
iki yakası kuş uçuşu 1-2 km'dir ama arada köprü/Marmaray yoksa ulaşım yarım
saati bulur. Bu yüzden mesafe değil, raylı sistem ağı üzerinde **aktarmalı
istasyon sayısı** temel alınır.
"""

import heapq
import json
import math
import re

from app.config import RAW_DIR
from app.heatmap import MIN_LISTINGS, classify

TRANSIT_PATH = RAW_DIR / "transit_stations.json"

# Bir mahallenin merkezi bir istasyona bu mesafeden yakınsa "raylı sisteme
# yürüme mesafesinde" sayılır (km, kuş uçuşu). ~1.2 km, rahat bir yürüyüş
# üst sınırı; sokak payıyla ~18 dakika (bkz. WALK_MINUTES_PER_KM).
WALK_KM = 1.2

# Ağ üzerinde iki istasyon arası "yakınlık" eşiği. Aktarma dahil bu kadar
# duraktan uzaktaki istasyonlar "kolay ulaşılır" sayılmaz.
MAX_HOPS = 12

# Aktarma, aynı hatta bir durak ilerlemekten daha maliyetli (bekleme + yürüme).
# Durak = 1 birim, aktarma = TRANSFER_COST birim.
TRANSFER_COST = 5

# Kapıdan kapıya süre tahmini (dakika). Sıralama ve kullanıcıya gösterilen
# "~X dk" buradan gelir. Üçü de kaba ortalama, ölçüm değil:
# * durak başı 2 dk: M2 Yenikapı–Hacıosman 16 istasyonu ~32 dakikada gider;
# * aktarma, ağ maliyetiyle tutarlı olsun diye TRANSFER_COST durak = 10 dk
#   (aktarma koridoru + bekleme);
# * yürüme 15 dk/km: 5 km/sa yürüyüş, kuş uçuşu mesafeye %25 sokak payı.
#   Yokuş hesaba katılmaz (Bebek'ten Etiler'e çıkış gibi); arayüz bunu söyler.
MINUTES_PER_STOP = 2
MINUTES_PER_TRANSFER = TRANSFER_COST * MINUTES_PER_STOP
WALK_MINUTES_PER_KM = 15

# Kapıdan kapıya bundan uzun süren mahalle "yakın alternatif" sayılmaz.
MAX_MINUTES = 45

# Bütçeye uyan yakın mahalle yoksa, bütçeyi aşsalar da gösterilecek en ucuz
# yakın seçenek sayısı. Sessizce boş liste dönmek yerine "en az şu kadar
# gerekiyor" demek, öğrenci bütçesinde asıl işe yarayan cevap.
CHEAPEST_FALLBACK = 3

# İstanbul'da işleyen her raylı hat bir hat koduyla anılır (M1A, T4, F3;
# Marmaray OSM'de B1). OSM'de kodsuz gelen ilişkiler yapımı süren ya da
# planlanan hatlar: indirilen veride "Üsküdar-Cevizli" tramvayı (açılışı
# 2027'ye kalan Üsküdar–Kadıköy–Maltepe hattı) 33 durakla ağda duruyor ve
# Kadıköy yakasına henüz olmayan bir hat üzerinden öneri üretiyordu.
LINE_CODE_RE = re.compile(r"^[MTFB]\d+[A-Z]?$")


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
    if not geometry:  # GeoJSON'da geometry null olabilir
        return None
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
        # Kodsuz (yapımı süren/planlanan) hatlar ağa hiç girmez; yalnızca
        # onlarda bulunan duraklar da hiçbir mahalleye bağlanmaz.
        self.lines = [line for line in lines if LINE_CODE_RE.match(line["ref"])]
        self.served = sorted(
            {index for line in self.lines for index in line["stations"]}
        )
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
        """Kaynak istasyondan kolay ulaşılan istasyonlar.

        {indeks: (maliyet, durak, aktarma)}; kaynağın kendisi (0, 0, 0).
        Her istasyona hangi hatla ulaşıldığını takip eden Dijkstra: bir kenarı
        geçmek 1 birim, ama gelinen hattan farklı bir hatta binmek ek olarak
        TRANSFER_COST öder. Böylece "3 durak ötede ama 2 aktarmalı" bir yer,
        "5 durak ötede ama aktarmasız" bir yerden pahalı çıkar. Durak ve
        aktarma sayısı ayrıca taşınır: kullanıcıya "8 durak" yerine "3 durak,
        1 aktarma" denebilsin ve süre tahmini ikisinden kurulabilsin.
        """
        # Durum: (istasyon, o istasyona giriş hattı). Aynı istasyona farklı
        # hatla ulaşmak farklı devam maliyetleri doğurduğu için hat durumun
        # parçası olmalı. Heap'teki "" hattı, henüz binilmemiş kaynağı temsil
        # eder (None, str ile karşılaştırılamadığı için).
        best = {(source, ""): 0}
        frontier = [(0, 0, 0, source, "")]
        result = {source: (0, 0, 0)}

        while frontier:
            cost, stops, transfers, node, via_line = heapq.heappop(frontier)
            if best.get((node, via_line), math.inf) < cost:
                continue

            if node not in result or cost < result[node][0]:
                result[node] = (cost, stops, transfers)
            if cost >= max_hops:
                continue

            for neighbor, refs in self._adjacency[node].items():
                for ref in refs:
                    change = 1 if via_line and ref != via_line else 0
                    new_cost = cost + 1 + TRANSFER_COST * change
                    if new_cost > max_hops:
                        continue
                    state = (neighbor, ref)
                    if new_cost < best.get(state, math.inf):
                        best[state] = new_cost
                        heapq.heappush(frontier, (
                            new_cost, stops + 1, transfers + change, neighbor, ref,
                        ))

        return result

    def stations_near(self, lat, lon, max_km=WALK_KM):
        """[(istasyon_indeksi, km), ...] — yürüme mesafesindekiler, yakından uzağa."""
        near = []
        for index in self.served:
            station = self.stations[index]
            km = haversine_km(lat, lon, station["lat"], station["lon"])
            if km <= max_km:
                near.append((index, km))
        near.sort(key=lambda item: item[1])
        return near

    def nearest_station(self, lat, lon):
        """(istasyon_indeksi, km) — noktaya en yakın istasyon."""
        best_index, best_km = None, math.inf
        for index in self.served:
            station = self.stations[index]
            km = haversine_km(lat, lon, station["lat"], station["lon"])
            if km < best_km:
                best_index, best_km = index, km
        return best_index, best_km


def walk_minutes(km):
    """Kuş uçuşu mesafeden yaklaşık yürüme süresi (dakika)."""
    return km * WALK_MINUTES_PER_KM


class AccessibilityIndex:
    """Mahalleleri raylı sistem ağına bağlar ve alternatif semt önerir.

    Kurulum (sunucu açılışında bir kez):
    * her mahallenin merkezini hesapla
    * merkezin yürüme mesafesindeki BÜTÜN istasyonları bul. Yalnızca en
      yakını almak, iki hattın arasında kalan bir mahalleyi (örn. Marmaray'a
      400 m, M4'e 900 m) yalnızca birinden ulaşılabilir sayıyor ve diğer
      hat üzerindeki hedefe aktarmalı, uzun bir yol çiziyordu.
    * her istasyonun kolay-ulaşılır komşu istasyonlarını ilk istekte hesapla
      ve önbelleğe al
    """

    def __init__(self, network, features, market_prices):
        self.network = network
        # {mahalle_id: {"name","district","lat","lon","walk_km","price",
        #               "listing_count","stations": [(istasyon, km), ...]}}
        self.places = {}
        # istasyon indeksi -> [(mahalle_id, km), ...]
        self._by_station = {}
        self._reach_cache = {}

        for feature in features:
            props = feature["properties"]
            centroid = polygon_centroid(feature["geometry"])
            if centroid is None:
                continue
            lat, lon = centroid
            near = network.stations_near(lat, lon)
            walk_km = near[0][1] if near else network.nearest_station(lat, lon)[1]

            place = {
                "id": props["id"],
                "name": props.get("neighborhood", ""),
                "district": props.get("district", ""),
                "lat": lat,
                "lon": lon,
                "walk_km": round(walk_km, 2),
                "price": market_prices.get(props["id"]),
                "listing_count": props.get("listing_count"),
                "stations": near,
            }
            self.places[props["id"]] = place
            for station_index, km in near:
                self._by_station.setdefault(station_index, []).append(
                    (props["id"], km)
                )

    def _reach(self, station_index):
        if station_index not in self._reach_cache:
            self._reach_cache[station_index] = self.network.easy_reach(station_index)
        return self._reach_cache[station_index]

    def _routes_from(self, target):
        """Hedefe kolay ulaşılan mahalleler ve en kısa tahmini yolları.

        {mahalle_id: yol}. Yol, hedefin ve adayın yürüme mesafesindeki
        istasyon çiftleri arasından kapıdan kapıya en kısa süreli olanıdır;
        süre iki uçtaki yürüme + durak + aktarmadan oluşur.
        """
        routes = {}
        for target_station, target_km in target["stations"]:
            reach = self._reach(target_station)
            for station, (_cost, stops, transfers) in reach.items():
                for place_id, km in self._by_station.get(station, []):
                    minutes = (walk_minutes(target_km) + walk_minutes(km)
                               + stops * MINUTES_PER_STOP
                               + transfers * MINUTES_PER_TRANSFER)
                    if place_id in routes and routes[place_id]["minutes"] <= minutes:
                        continue
                    routes[place_id] = {
                        "minutes": minutes,
                        "stops": stops,
                        "transfers": transfers,
                        "walk_km": km,
                    }
        return routes

    def recommend(self, target_id, budget, limit=6):
        """Hedef mahalleye raylı sistemle yakın, ondan ucuz ve bütçeye uyan
        alternatifler.

        Bir mahalle şu üç şartla alternatif sayılır:
        1. hedefe raylı sistemle kapıdan kapıya ~MAX_MINUTES dakikadan kısa
           sürede ulaşılıyor (her iki uç da istasyona yürüme mesafesinde,
           aradaki yol en fazla bir aktarmalı — bkz. MAX_HOPS);
        2. hedeften ucuz (hedeften pahalı bir "alternatif" öneri değildir);
        3. bütçeye uyuyor ya da haritadaki gibi "sınırda" (bütçenin %20
           üstüne kadar; heatmap.BORDERLINE_RATIO).

        Sonuç önce tahmini süreye, eşitlikte ucuzluğa göre sıralanır. Hiçbir
        aday bütçeye uymuyorsa liste boş döner ama `cheapest` en ucuz
        CHEAPEST_FALLBACK yakın seçeneği taşır; istemci "bu bütçeyle yok,
        en az şu kadar gerekiyor" diyebilsin.
        """
        target = self.places.get(target_id)
        if target is None:
            return {"error": "Mahalle bulunamadı."}
        if not target["stations"]:
            return {
                "target": _public(target),
                "reachable": False,
                "reason": "not_near_rail",
                "budget": budget,
                "max_minutes": MAX_MINUTES,
                "recommendations": [],
                "cheapest": [],
            }

        target_price = target["price"]
        candidates = []
        for place_id, route in self._routes_from(target).items():
            if place_id == target_id or route["minutes"] > MAX_MINUTES:
                continue
            place = self.places[place_id]
            price = place["price"]
            if price is None:
                continue
            if target_price is not None and price >= target_price:
                continue
            candidates.append({
                **_public(place),
                "minutes": round(route["minutes"]),
                "stops": route["stops"],
                "transfers": route["transfers"],
                "walk_minutes": round(walk_minutes(route["walk_km"])),
                "status": classify(price, budget),
                "saving": round(target_price - price) if target_price else None,
            })

        fits = [c for c in candidates if c["status"] != "expensive"]
        fits.sort(key=lambda c: (c["minutes"], c["price"]))

        cheapest = []
        if not fits:
            cheapest = sorted(candidates, key=lambda c: (c["price"], c["minutes"]))
            cheapest = [
                c | {"over_budget": round(c["price"] - budget)}
                for c in cheapest[:CHEAPEST_FALLBACK]
            ]

        return {
            "target": _public(target),
            "reachable": True,
            "budget": budget,
            "max_minutes": MAX_MINUTES,
            "recommendations": fits[:limit],
            "cheapest": cheapest,
        }


def _public(place):
    """Mahalle kaydından istemciye gidecek alanları seçer."""
    count = place["listing_count"]
    return {
        "id": place["id"],
        "name": place["name"],
        "district": place["district"],
        "price": place["price"],
        "low_confidence": count is not None and count < MIN_LISTINGS,
        "lat": round(place["lat"], 5),
        "lon": round(place["lon"], 5),
    }
