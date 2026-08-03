"""İstanbul bütçe ısı haritası API'si."""

import json
import os
from contextlib import asynccontextmanager
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (
    MARKET_VALUES_CSV,
    MODEL_PATH,
    NEIGHBORHOOD_GEOJSON,
    UPLOADS_DIR,
)
from app.admin import router as admin_router
from app.auth import router as auth_router
from app.db import init_db
from app.heatmap import (
    STATUS_STYLES,
    annotate_features,
    build_budget_heatmap,
    index_market_prices,
)
from app import locations
from app.indexing import DATA_PERIOD, is_configured, rent_index
from app.listings import router as listings_router
from app.messages import router as messages_router
from app.reports import router as reports_router
from app.swipes import router as swipes_router
from app.uploads import router as uploads_router
from app.pricing import BOUNDS, build_features
from app.transit import TRANSIT_PATH, AccessibilityIndex, TransitNetwork


class EstimateRequest(BaseModel):
    """Adil fiyat tahmini için ilan özellikleri.

    Sınırlar `pricing.BOUNDS` ile aynı: model bu aralığın dışında eğitilmedi,
    dışarıda kalan girdilere verilecek cevap güvenilir olmaz.
    """

    district: str = Field(..., min_length=1)
    neighborhood: str = Field(..., min_length=1)
    room: int = Field(..., ge=BOUNDS["room"][0], le=BOUNDS["room"][1])
    living_room: int = Field(
        1, ge=BOUNDS["living room"][0], le=BOUNDS["living room"][1]
    )
    area: float = Field(..., ge=BOUNDS["area (m2)"][0], le=BOUNDS["area (m2)"][1])
    age: int = Field(..., ge=BOUNDS["age"][0], le=BOUNDS["age"][1])
    floor: int = Field(..., ge=BOUNDS["floor"][0], le=BOUNDS["floor"][1])
    # Opsiyonel: verilirse tahmini bantla karşılaştırıp yorum döneriz.
    asking_price: float | None = Field(None, gt=0)
    # "flat": istenen fiyat tüm dairenin kirası; "room": tek odanın payı
    # (ev arkadaşı ilanlarında oda kiraya verilir, kıyas oda payıyla yapılır).
    basis: Literal["flat", "room"] = "flat"

# Sunucu açılışında doldurulur.
STATE: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ağır veriyi süreç başına bir kez yükler ve indeksler."""
    print("🚀 Veriler yükleniyor...")
    # Yeni tablolar create_all ile doğar; var olan tablolara eksik sütunlar
    # init_db içinden çağrılan run_migrations ile eklenir (üretimde canlı
    # Postgres var, veri kaybı olmadan).
    init_db()
    with NEIGHBORHOOD_GEOJSON.open(encoding="utf-8") as f:
        geojson = json.load(f)

    df = pd.read_csv(MARKET_VALUES_CSV)
    matched = annotate_features(geojson, df)
    total = len(geojson.get("features", []))

    # Harita fiyatları da bugüne endekslenir. Endeksleme yalnızca adil fiyat
    # uçlarına uygulandığı sürece iki özellik birbiriyle çelişiyordu: danışman
    # Kadıköy'de oda payını bugünün lirasıyla söylerken harita aynı semti
    # DATA_PERIOD (2025-02) fiyatıyla boyuyor, yani bütçeyi olduğundan yeterli
    # gösteriyordu. Tek yerde, veri yüklenirken uygulanır ki /api/geojson ve
    # /api/heatmap aynı sayıyı görsün.
    index_market_prices(geojson, rent_index()[0])

    STATE["geojson"] = geojson
    # Sıcak yolda pandas'a hiç dokunmamak için fiyatları düz listeye alıyoruz.
    STATE["prices"] = [
        f["properties"]["avg_price"] for f in geojson.get("features", [])
    ]
    STATE["counts"] = [
        f["properties"].get("listing_count") for f in geojson.get("features", [])
    ]
    if total:
        print(f"✅ Hazır: {total} mahalleden {matched} tanesi fiyat verisiyle "
              f"eşleşti ({matched / total * 100:.1f}%).")
    else:
        print("⚠️  GeoJSON boş — harita uçları veri döndürmeyecek.")

    # Adil fiyat modeli opsiyonel: yoksa harita yine de çalışsın.
    if MODEL_PATH.exists():
        STATE["model"] = joblib.load(MODEL_PATH)
        print(f"✅ Adil fiyat modeli yüklendi "
              f"(medyan sapma %{STATE['model']['served_medape']:.1f}).")
    else:
        print(f"⚠️  Model yok ({MODEL_PATH}) — /api/estimate devre dışı. "
              f"Eğitmek için: python -m scripts.train_model")

    # /api/locations yanıtı sabit; ilk istekte değil burada kurulur.
    # Model varsa liste onun tanıdığı mahallelerle sınırlanır (bkz. locations.py).
    locations.clear_cache()
    STATE["locations"] = locations.get_locations()
    print(f"✅ Konum listesi hazır: {len(STATE['locations'])} ilçe, "
          f"{sum(len(d['neighborhoods']) for d in STATE['locations'])} mahalle.")

    # Toplu taşıma erişilebilirliği opsiyonel: veri yoksa /api/alternatives kapalı.
    if TRANSIT_PATH.exists():
        network = TransitNetwork.load()
        prices_by_id = {
            f["properties"]["id"]: f["properties"]["avg_price"]
            for f in geojson.get("features", [])
        }
        STATE["access"] = AccessibilityIndex(
            network, geojson.get("features", []), prices_by_id
        )
        walkable = sum(
            1 for p in STATE["access"].places.values() if p["walk_km"] <= 1.2
        )
        print(f"✅ Toplu taşıma ağı yüklendi ({len(network.stations)} istasyon; "
              f"{walkable} mahalle yürüme mesafesinde).")
    else:
        print(f"⚠️  Toplu taşıma verisi yok ({TRANSIT_PATH.name}) — "
              f"/api/alternatives devre dışı. İndirmek için: "
              f"python -m scripts.fetch_transit")

    yield
    STATE.clear()


# ---------------------------------------------------------------------------
# Güvenlik ara katmanları
# ---------------------------------------------------------------------------
#
# İkisi de saf ASGI ara katmanıdır (BaseHTTPMiddleware DEĞİL). Sebep: gövdeyi
# akış halinde okumak ve StaticFiles yanıtlarını tamponlamadan geçirmek
# gerekiyor; BaseHTTPMiddleware her yanıtı bir anyio kanalına kopyalar,
# yani hem yavaşlar hem de /uploads/ akışını belleğe alır.

# Tüm yanıtlara eklenen başlıklar. Değerler sabit, istek başına yeniden
# üretilmez (aşağıdaki liste modül yüklenirken bir kez kurulur).
_SECURITY_HEADERS: list[tuple[bytes, bytes]] = [
    # Tarayıcı Content-Type'ı tahmin etmeye çalışmasın. JSON uçları için de
    # gerekli: nosniff olmadan bir yanıt gövdesi HTML sanılıp çalıştırılabilir.
    (b"x-content-type-options", b"nosniff"),
    # Çapraz kaynağa yalnızca origin sızsın; ilan/profil id'leri yol içinde.
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    # API'nin çerçevelenmesi için hiçbir meşru sebep yok (clickjacking).
    (b"x-frame-options", b"DENY"),
    # Tarayıcı özelliklerini kapat: API bunların hiçbirini kullanmıyor.
    (
        b"permissions-policy",
        b"accelerometer=(), autoplay=(), camera=(), display-capture=(), "
        b"encrypted-media=(), geolocation=(), gyroscope=(), magnetometer=(), "
        b"microphone=(), midi=(), payment=(), usb=()",
    ),
]

# HSTS yalnızca istek https ise gönderilir: düz http üzerinden gönderilmesi
# hem anlamsız hem de yerel geliştirmede (http://127.0.0.1:8000) tarayıcıyı
# kilitler. `preload` BİLEREK yok — preload listesine girmek geri alması aylar
# süren bir taahhüttür ve alan adının TÜM alt alanlarını kapsar.
_HSTS = (b"strict-transport-security", b"max-age=63072000; includeSubDomains")

# /uploads/ altındaki kullanıcı dosyalarına eklenen ek başlıklar (M4).
# Content-Disposition: attachment, yüklenen bir dosyanın API kaynağında
# BELGE olarak açılmasını engeller (saklı XSS). <img src> ile gösterime
# etkisi yoktur: Content-Disposition yalnızca üst seviye gezinmede
# uygulanır, alt kaynak (img/script/css) yüklemelerinde tarayıcı bunu
# yok sayar. VARSAYIM DEĞİL, ölçüldü: Chrome 150 ile hem aynı origin'de hem
# de çapraz origin'de (üretim topolojisi: Vercel sayfası -> api.evdes.tr
# resmi) attachment başlıklı resim sorunsuz çizildi, naturalWidth doğru
# geldi. Ayrıntı: DEPLOY.md §5.
_UPLOAD_HEADERS: list[tuple[bytes, bytes]] = [
    (b"content-disposition", b"attachment"),
    # Fotoğraflar başka bir origin'deki (Vercel) arayüzden yükleniyor;
    # CORP'u açıkça yazmak, ileride COEP açan bir sayfanın resimleri
    # sessizce engellemesini önler.
    (b"cross-origin-resource-policy", b"cross-origin"),
]


class SecurityHeadersMiddleware:
    """Her HTTP yanıtına güvenlik başlıklarını ekler.

    Var olan bir başlığı EZMEZ: bir uç bilinçli olarak farklı bir değer
    yazdıysa (örn. gömülebilir bir yanıt) o değer korunur.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        extra = list(_SECURITY_HEADERS)
        # Ters vekil arkasında scope["scheme"] --proxy-headers sayesinde
        # https olur; olmadığı kurulumlar için X-Forwarded-Proto'ya da bakılır.
        if scope.get("scheme") == "https" or _forwarded_https(scope):
            extra.append(_HSTS)
        if scope.get("path", "").startswith("/uploads/"):
            extra += _UPLOAD_HEADERS

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                present = {name.lower() for name, _ in headers}
                headers.extend(
                    (name, value) for name, value in extra if name not in present
                )
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _forwarded_https(scope) -> bool:
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-proto":
            # Zincirlenmiş vekillerde "https, http" olabilir; ilki istemciye en yakın.
            return value.split(b",")[0].strip().lower() == b"https"
    return False


# İstek gövdesi üst sınırı. En büyük meşru gövde fotoğraf yüklemesidir
# (uploads.MAX_BYTES = 5 MB) + multipart çerçevesi; 6 MB rahat pay bırakır.
MAX_REQUEST_BYTES = int(os.getenv("MAX_REQUEST_BYTES", str(6 * 1024 * 1024)))


class _BodyTooLarge(Exception):
    """Akış halinde okunan gövde sınırı aştı."""


async def _send_413(send) -> None:
    body = b'{"detail":"Istek govdesi cok buyuk."}'
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Uygulama katmanında istek gövdesi üst sınırı (H1).

    İki ayrı durum var:

    1. `Content-Length` bildirilmiş: değeri okumak yeter, gövdeye hiç
       dokunmadan 413 döneriz. Sınırın altındaysa ara katman TAMAMEN devre
       dışı kalır — `receive` sarmalanmaz, normal isteklere ölçülebilir bir
       maliyet binmez. Bildirilen uzunluğu sunucu (h11) zaten zorlar.

    2. `Content-Length` YOK (`Transfer-Encoding: chunked`): boyut önceden
       bilinemez. Bu durumda `receive` sarmalanır, okunan bayt sayılır ve
       sınır aşılır aşılmaz istek kesilir. Eskiden chunked gövde tüm boyut
       kontrollerini atlıyordu; uploads.py'deki 5 MB kontrolü ancak dosya
       diske yazıldıktan SONRA çalışıyordu.

    Bu, tam çözümün yerine geçmez: sunucuya kadar gelen baytlar yine de ağ
    ve bellek tüketir. Gerçek savunma ters vekilde (`client_max_body_size`)
    olmalı — bkz. DEPLOY.md §5.
    """

    # Gövdesi olmayan yöntemler: sarmalamaya hiç girmeyiz.
    _BODYLESS = frozenset({"GET", "HEAD", "OPTIONS", "DELETE", "TRACE"})

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") in self._BODYLESS:
            await self.app(scope, receive, send)
            return

        declared = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                declared = value
                break

        if declared is not None:
            if declared.isdigit() and int(declared) > self.max_bytes:
                await _send_413(send)
                return
            # Hızlı yol: uzunluk bildirilmiş ve sınırın altında.
            await self.app(scope, receive, send)
            return

        total = 0
        too_large = False
        forwarded = False

        async def counting_receive():
            # Sınır aşılınca istisna FIRLATILMAZ: istisna uygulamanın gövde
            # ayrıştırıcısında yakalanıp 400'e dönüşüyordu ve bizim 413'ümüz
            # hiç görünmüyordu. Bunun yerine bağlantı kopmuş gibi davranıp
            # uygulamanın yanıtını bastırıyoruz.
            nonlocal total, too_large
            if too_large:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    too_large = True
                    return {"type": "http.disconnect"}
            return message

        async def gated_send(message):
            # Sınır aşıldıysa uygulamanın ürettiği yanıt (genelde 400) dışarı
            # çıkmaz; yerine tek doğru cevabı biz veririz.
            nonlocal forwarded
            if too_large:
                return
            forwarded = True
            await send(message)

        await self.app(scope, counting_receive, gated_send)
        if too_large and not forwarded:
            await _send_413(send)


app = FastAPI(title="İstanbul Emlak Isı Haritası", lifespan=lifespan)
app.include_router(listings_router)
app.include_router(auth_router)
app.include_router(swipes_router)
app.include_router(messages_router)
app.include_router(uploads_router)
app.include_router(reports_router)
app.include_router(admin_router)

# Yüklenen fotoğrafların statik servisi
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# --- Ara katman sırası ---------------------------------------------------
# add_middleware TERS sırayla uygulanır: EN SON eklenen EN DIŞTAKİdir.
# Aşağıdaki dört çağrı şu zinciri kurar (dıştan içe):
#
#   SecurityHeaders -> CORS -> BodySizeLimit -> GZip -> yönlendirici
#
# Neden bu sıra:
#   * SecurityHeaders EN DIŞTA: CORS preflight (OPTIONS) isteğini kendi içinde
#     yanıtlayıp kısa devre yapar, yani CORS'un İÇİNDEKİ hiçbir katmana
#     uğramaz. SecurityHeaders içeride kalsaydı preflight yanıtları güvenlik
#     başlıklarını hiç almazdı. Dışta olması CORS başlıklarını ezmez: var olan
#     başlığın üstüne yazmıyor.
#   * CORS onun içinde: alt katmanların ürettiği hata yanıtları (ör. 413) da
#     CORS başlığı almalı, yoksa tarayıcı bunu kullanıcıya "CORS hatası" diye
#     gösterir ve gerçek sebep kaybolur.
#   * BodySizeLimit GZip'in dışında: gövde kontrolü sıkıştırma katmanına
#     girmeden, mümkün olan en erken noktada yapılır.
#   * GZip en içte: yalnızca yönlendiricinin ürettiği yanıtı sıkıştırır.

# Yanıtlar büyük GeoJSON içerdiği için sıkıştırma kritik (~4 MB -> ~700 KB).
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_REQUEST_BYTES)
# Geliştirme için yerel origin'ler; yayında CORS_ORIGINS ile geçersiz kılınır
# (virgülle ayrılmış liste, örn. "https://app.example.com,https://example.com").
_DEFAULT_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    # Vite dev sunucusu (frontend/): React roommate uygulaması
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]

_env_origins = os.getenv("CORS_ORIGINS", "").strip()

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        [o.strip() for o in _env_origins.split(",") if o.strip()]
        if _env_origins
        else _DEFAULT_ORIGINS
    ),
    # PATCH (ilan/profil güncelleme) ve DELETE (ilan kaldırma) da kullanılıyor.
    allow_methods=["*"],
    allow_headers=["*"],
)
# EN SON eklenen EN DIŞTAKİdir: güvenlik başlıkları CORS'u da sarar, böylece
# preflight yanıtları da başlıkları alır (bkz. yukarıdaki sıra açıklaması).
app.add_middleware(SecurityHeadersMiddleware)


# HEAD de kabul edilir: Render'ın sağlık yoklaması ve keep-alive işi kökü HEAD
# ile çağırıyor, FastAPI ise GET rotasına HEAD eklemediği için loglar 405 ile
# doluyordu. Gövde zaten dönmez, maliyeti yok.
@app.api_route("/", methods=["GET", "HEAD"])
async def index():
    """Kök adres: API tanıtımı. Asıl arayüz React uygulamasında (frontend/)."""
    return {
        "name": app.title,
        "docs": "/docs",
        "endpoints": [
            "/api/geojson",
            "/api/heatmap",
            "/api/legend",
            "/api/locations",
            "/api/estimate",
            "/api/alternatives",
            "/api/listings",
            "/api/auth",
            "/api/swipes",
            "/api/matches",
            "/api/reports",
            "/api/admin",
        ],
    }


@app.get("/api/geojson")
async def get_geojson():
    """Mahalle sınırlarını ve fiyatlarını döndürür.

    Bu yanıt bütçeden bağımsızdır, bu yüzden istemci tarafından bir kez
    indirilip önbelleğe alınabilir.
    """
    if "geojson" not in STATE:
        raise HTTPException(status_code=503, detail="Veriler henüz yüklenmedi.")
    return JSONResponse(
        STATE["geojson"],
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/heatmap")
async def get_heatmap(
    budget: float = Query(..., gt=0, le=10_000_000, description="Aylık bütçe (TL)")
):
    """Verilen bütçe için mahalle durum listesini döndürür (kompakt)."""
    if "prices" not in STATE:
        raise HTTPException(status_code=503, detail="Veriler henüz yüklenmedi.")
    return build_budget_heatmap(STATE["prices"], budget, STATE.get("counts"))


@app.get("/api/legend")
async def get_legend():
    """Renk/etiket sözlüğü — istemcinin renkleri kopyalamasına gerek kalmasın."""
    return STATUS_STYLES


@app.get("/api/locations")
async def get_locations():
    """İlan formu için ilçe -> mahalle listesi.

    Model yüklüyse yalnızca onun TANIDIĞI mahalleler döner; tanımadığı bir
    mahalle seçilse tahmin ilçe geneline düşerdi (bkz. app/locations.py).
    Yanıt sürece göre sabittir, bu yüzden uzun süreli önbelleklenebilir.
    """
    return JSONResponse(
        STATE.get("locations") or locations.get_locations(),
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _require_model():
    model = STATE.get("model")
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Adil fiyat modeli yüklü değil. Önce 'python train_model.py' çalıştır.",
        )
    return model


@app.post("/api/estimate")
async def estimate(payload: EstimateRequest):
    """İlan özelliklerinden adil kira aralığı tahmin eder."""
    model = _require_model()

    features = build_features(
        pd.DataFrame([{
            "room": payload.room,
            "living room": payload.living_room,
            "area (m2)": payload.area,
            "age": payload.age,
            "floor": payload.floor,
            "district": payload.district.strip(),
            "neighborhood": payload.neighborhood.strip(),
        }]),
        model["categories"],
    )

    band = {
        label: float(np.exp(m.predict(features)[0]))
        for label, m in model["models"].items()
    }
    # Çeyreklik modelleri bağımsız eğitildiği için nadiren sıra bozulabilir.
    low, mid, high = sorted(band.values())

    # Model eğitim dönemi liralarıyla konuşur; TÜFE ile bugüne endeksle.
    factor, indexed_to = rent_index()
    low, mid, high = low * factor, mid * factor, high * factor

    # Ev arkadaşı senaryosu: dairenin kirası oda başına bölüşülür (yatak odası
    # sayısı kadar kişi). 1+1/1+0'da bölüşme olmaz, pay = tüm kira.
    share = max(payload.room, 1)
    room_low, room_mid, room_high = low / share, mid / share, high / share

    # Eğitimde görülmemiş mahalle: tahmin ilçe geneline dayanır, bunu söylemeliyiz.
    known_neighborhood = (
        payload.neighborhood.strip() in set(model["categories"]["neighborhood"])
    )

    response = {
        "fair_low": round(low),
        "fair_mid": round(mid),
        "fair_high": round(high),
        "room_low": round(room_low),
        "room_mid": round(room_mid),
        "room_high": round(room_high),
        "room_share": share,
        "median_error_pct": round(model["served_medape"], 1),
        "known_neighborhood": known_neighborhood,
        "index_factor": round(factor, 4),
        "data_period": DATA_PERIOD,
        "indexed_to": indexed_to,
        "indexed": is_configured(),
        "basis": payload.basis,
    }

    if payload.asking_price is not None:
        asking = payload.asking_price
        # Oda bazında kıyas: istenen fiyat tek odanın payıyla karşılaştırılır.
        c_low, c_mid, c_high = (
            (room_low, room_mid, room_high)
            if payload.basis == "room"
            else (low, mid, high)
        )
        deviation = (asking - c_mid) / c_mid * 100
        if asking < c_low:
            verdict = "below"
        elif asking > c_high:
            verdict = "above"
        else:
            verdict = "fair"
        response |= {
            "asking_price": asking,
            "verdict": verdict,
            "deviation_pct": round(deviation, 1),
        }

    return response


@app.get("/api/alternatives")
async def alternatives(
    neighborhood_id: int = Query(..., ge=0, description="Hedef mahalle id'si"),
    budget: float = Query(..., gt=0, le=10_000_000, description="Aylık bütçe (TL)"),
):
    """Hedef mahalleye raylı sistemle yakın, bütçeye uygun alternatifler.

    id, /api/geojson içindeki her feature'ın properties.id değeridir.
    """
    access = STATE.get("access")
    if access is None:
        raise HTTPException(
            status_code=503,
            detail="Toplu taşıma verisi yüklü değil. "
                   "Önce 'python -m scripts.fetch_transit' çalıştır.",
        )
    result = access.recommend(neighborhood_id, budget)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


if __name__ == "__main__":
    import uvicorn

    # Yayın ortamları (Render/Railway) PORT verir; yerelde 8000.
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
    )
