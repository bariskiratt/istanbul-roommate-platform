"""Proje genelindeki dosya yolları.

Yollar `__file__` üzerinden çözülüyor; böylece betikler hangi dizinden
çalıştırılırsa çalıştırılsın veriyi buluyor (cwd'ye bağımlı değil).
"""

from pathlib import Path

# app/config.py -> app/ -> proje kökü
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
WEB_DIR = BASE_DIR / "web"

# Ham veri
LISTINGS_CSV = RAW_DIR / "istanbulApartmentForRent.csv"
NEIGHBORHOOD_GEOJSON = RAW_DIR / "mahalle_geojson.json"
DISTRICT_GEOJSON = RAW_DIR / "ilce_geojson.json"

# Üretilen veri
MARKET_VALUES_CSV = PROCESSED_DIR / "neighborhood_market_values.csv"

# Eğitilmiş model
MODEL_PATH = MODELS_DIR / "fair_price_model.joblib"

# Arayüz
INDEX_HTML = WEB_DIR / "index.html"
