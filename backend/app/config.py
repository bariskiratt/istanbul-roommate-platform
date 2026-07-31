"""Proje genelindeki dosya yolları.

Yollar `__file__` üzerinden çözülüyor; böylece betikler hangi dizinden
çalıştırılırsa çalıştırılsın veriyi buluyor (cwd'ye bağımlı değil).
"""

import os
from pathlib import Path

# app/config.py -> app/ -> proje kökü
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

# Ham veri
LISTINGS_CSV = RAW_DIR / "istanbulApartmentForRent.csv"
NEIGHBORHOOD_GEOJSON = RAW_DIR / "mahalle_geojson.json"

# Üretilen veri
MARKET_VALUES_CSV = PROCESSED_DIR / "neighborhood_market_values.csv"

# Eğitilmiş model
MODEL_PATH = MODELS_DIR / "fair_price_model.joblib"

# Uygulama veritabanı (ilanlar; ileride kullanıcı/eşleşme/mesaj)
DB_PATH = DATA_DIR / "app.db"

# Yönetici hesaplar (virgülle ayrılmış e-postalar). Şimdilik yalnızca
# "Evler" sekmesinin görünürlüğünü belirler; ileride moderasyon için.
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv(
        "ADMIN_EMAILS", "bariskirat5@gmail.com,baris.kirat@std.yildiz.edu.tr"
    ).split(",")
    if e.strip()
}

# Kullanıcı fotoğrafları (yerelde üretilir, git'e girmez).
# Yayında kalıcı disk bağlanan yolu UPLOADS_DIR env ile ver.
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", DATA_DIR / "uploads"))
