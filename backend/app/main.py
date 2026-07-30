"""İstanbul bütçe ısı haritası API'si."""

import json
import os
from contextlib import asynccontextmanager

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import (
    MARKET_VALUES_CSV,
    MODEL_PATH,
    NEIGHBORHOOD_GEOJSON,
)
from app.auth import router as auth_router
from app.db import init_db
from app.heatmap import STATUS_STYLES, annotate_features, build_budget_heatmap
from app.listings import router as listings_router
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

# Sunucu açılışında doldurulur.
STATE: dict = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ağır veriyi süreç başına bir kez yükler ve indeksler."""
    print("🚀 Veriler yükleniyor...")
    init_db()
    with NEIGHBORHOOD_GEOJSON.open(encoding="utf-8") as f:
        geojson = json.load(f)

    df = pd.read_csv(MARKET_VALUES_CSV)
    matched = annotate_features(geojson, df)
    total = len(geojson.get("features", []))

    STATE["geojson"] = geojson
    # Sıcak yolda pandas'a hiç dokunmamak için fiyatları düz listeye alıyoruz.
    STATE["prices"] = [
        f["properties"]["avg_price"] for f in geojson.get("features", [])
    ]
    print(f"✅ Hazır: {total} mahalleden {matched} tanesi fiyat verisiyle eşleşti "
          f"({matched / total * 100:.1f}%).")

    # Adil fiyat modeli opsiyonel: yoksa harita yine de çalışsın.
    if MODEL_PATH.exists():
        STATE["model"] = joblib.load(MODEL_PATH)
        # /api/locations yanıtı sabit; her istekte CSV okumamak için burada kur.
        known = set(STATE["model"]["categories"]["neighborhood"])
        grouped: dict[str, list[str]] = {}
        for row in df.itertuples(index=False):
            neighborhood = str(row.neighborhood).strip()
            if neighborhood in known:
                grouped.setdefault(str(row.district).strip(), []).append(neighborhood)
        STATE["locations"] = {d: sorted(set(n)) for d, n in sorted(grouped.items())}
        print(f"✅ Adil fiyat modeli yüklendi "
              f"(medyan sapma %{STATE['model']['served_medape']:.1f}).")
    else:
        print(f"⚠️  Model yok ({MODEL_PATH}) — /api/estimate devre dışı. "
              f"Eğitmek için: python -m scripts.train_model")

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


app = FastAPI(title="İstanbul Emlak Isı Haritası", lifespan=lifespan)
app.include_router(listings_router)
app.include_router(auth_router)

# Yanıtlar büyük GeoJSON içerdiği için sıkıştırma kritik (~4 MB -> ~700 KB).
app.add_middleware(GZipMiddleware, minimum_size=1024)
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
    # POST /api/estimate için OPTIONS+POST de gerekiyor.
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
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
        ],
    }


@app.get("/api/geojson")
async def get_geojson():
    """Mahalle sınırlarını ve fiyatlarını döndürür.

    Bu yanıt bütçeden bağımsızdır, bu yüzden istemci tarafından bir kez
    indirilip önbelleğe alınabilir.
    """
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
    return build_budget_heatmap(STATE["prices"], budget)


@app.get("/api/legend")
async def get_legend():
    """Renk/etiket sözlüğü — istemcinin renkleri kopyalamasına gerek kalmasın."""
    return STATUS_STYLES


@app.get("/api/locations")
async def get_locations():
    """Formu doldurmak için modelin tanıdığı ilçe -> mahalle listesi."""
    _require_model()
    return JSONResponse(
        STATE["locations"],
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

    # Eğitimde görülmemiş mahalle: tahmin ilçe geneline dayanır, bunu söylemeliyiz.
    known_neighborhood = (
        payload.neighborhood.strip() in set(model["categories"]["neighborhood"])
    )

    response = {
        "fair_low": round(low),
        "fair_mid": round(mid),
        "fair_high": round(high),
        "median_error_pct": round(model["served_medape"], 1),
        "known_neighborhood": known_neighborhood,
    }

    if payload.asking_price is not None:
        asking = payload.asking_price
        deviation = (asking - mid) / mid * 100
        if asking < low:
            verdict = "below"
        elif asking > high:
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

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
