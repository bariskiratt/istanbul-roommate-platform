"""Adil fiyat modeli için ortak veri hazırlama.

Eğitim (`train_model.py`) ve servis (`main.py`) aynı dönüşümleri kullanmalı,
yoksa modele eğitimdekinden farklı dağılımlı veri gider. Bu yüzden tüm
temizlik ve özellik üretimi tek yerde tutuluyor.
"""

import hashlib
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import LISTINGS_CSV

# Aylık kira bandı. Ham veride satılık ilanlar (23.000.000 TL'ye kadar) ve
# bin cinsinden girilmiş değerler (40, 60) karışık duruyor.
MIN_RENT, MAX_RENT = 3_000, 500_000

# Fiziksel olarak imkânsız değerler veriyi ciddi şekilde bozuyor:
# temizlemeden önce area max 178.158 m², age max 1864, living room max 363.
# Bu 43 satır (%0.5) atıldığında log(alan)-log(fiyat) korelasyonu
# 0.05'ten 0.59'a çıkıyor.
BOUNDS = {
    "area (m2)": (20, 1000),
    "age": (0, 100),
    "living room": (0, 5),
    "room": (1, 11),
    "floor": (-3, 30),
}

# Tahmin isteğinin ham alanları (API anahtarları). Backend ile AWS Lambda'daki
# tahmin servisi (services/fairprice) arasındaki sözleşme bu alanlardır, özellik
# matrisi değil: iki taraf da özellikleri aşağıdaki build_features ile kendi
# üretir, böylece tahmin servisine model ile uyumsuz bir matris gidemez.
ROW_FIELDS = ("room", "living_room", "area", "age", "floor", "district", "neighborhood")

# Modelin kimliğine giren kütüphaneler: model joblib (pickle) ile saklandığı
# için yükleyen tarafın sürümleri eğitendekiyle aynı olmalı.
MODEL_LIBRARIES = ("lightgbm", "scikit-learn", "pandas", "numpy")

NUMERIC_FEATURES = ["room", "living room", "log_area", "age", "floor"]
CATEGORICAL_FEATURES = ["district", "neighborhood"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "log_price"


def load_clean_data(path=LISTINGS_CSV):
    """Ham CSV'yi okur, yinelenenleri ve imkânsız değerleri eler."""
    df = pd.read_csv(path)
    df = df.drop_duplicates()

    df["district"] = df["district"].astype(str).str.strip()
    df["neighborhood"] = df["neighborhood"].astype(str).str.strip()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    df = df[df["price"].between(MIN_RENT, MAX_RENT)]
    for column, (low, high) in BOUNDS.items():
        df = df[df[column].between(low, high)]

    return df.reset_index(drop=True)


def build_features(df, categories=None):
    """Model matrisini üretir.

    Alan ve fiyat sağa çarpık olduğu için ikisinde de log kullanıyoruz; bu
    hem ilişkiyi doğrusallaştırıyor hem de hatayı mutlak TL yerine oransal
    hale getiriyor (2.000 TL'lik sapma 10.000 TL'lik evde ciddi, 100.000
    TL'lik evde önemsiz).

    `categories`: eğitimde görülen kategori listeleri. Serviste aynı
    kodlamanın kullanılması için modelle birlikte saklanır; eğitimde
    görülmemiş mahalle NaN olur ve ağaç modelleri bunu kendi işler.
    """
    X = pd.DataFrame(index=df.index)
    X["room"] = df["room"].astype(float)
    X["living room"] = df["living room"].astype(float)
    X["log_area"] = np.log(df["area (m2)"].astype(float))
    X["age"] = df["age"].astype(float)
    X["floor"] = df["floor"].astype(float)

    for column in CATEGORICAL_FEATURES:
        values = df[column].astype(str)
        if categories is None:
            dtype = pd.CategoricalDtype(sorted(values.unique()))
        else:
            dtype = pd.CategoricalDtype(categories[column])
            # Görülmemiş değeri açıkça NaN yap: pandas bunu astype içinde
            # sessizce yapmayı bırakıp hata vermeye geçiyor (Pandas4Warning).
            values = values.where(values.isin(categories[column]))
        X[column] = values.astype(dtype)

    return X[FEATURES]


def extract_categories(X):
    """Eğitimde kullanılan kategori listelerini çıkarır (serviste yeniden kullanmak için)."""
    return {c: list(X[c].cat.categories) for c in CATEGORICAL_FEATURES}


def feature_signature() -> str:
    """Bu kodla eğitilmiş modelleri tanıyan kısa parmak izi.

    Model artık eğitildiği yerden (GitHub Actions) başka yerlerde de
    yükleniyor: S3'ten indiren backend ve AWS Lambda'daki tahmin servisi.
    Bu dosyadaki özellik üretimi ya da kütüphane sürümleri değişmişse eski
    model sessizce yanlış tahmin verir (eğitim/servis kayması). Parmak izi bu
    dosyanın içeriğinden ve MODEL_LIBRARIES sürümlerinden üretilir; eğitim
    modele yazar, yükleyen taraf kendi hesapladığıyla karşılaştırır ve
    tutmayan modeli kullanmaz. Bilerek katı: yorum değişikliği de yeni bir
    imza demektir, bu da yalnızca modelin (birkaç saniyede) yeniden
    eğitilmesine yol açar.
    """
    digest = hashlib.sha256(Path(__file__).read_bytes())
    for package in MODEL_LIBRARIES:
        digest.update(f"|{package}=={version(package)}".encode())
    return digest.hexdigest()[:16]


def predict_band(model, rows):
    """Her satır için dairenin tamamının ham kira bandını döndürür.

    `rows`: ROW_FIELDS anahtarlı sözlükler. Dönüş: her satır için sıralı
    (low, mid, high) TL, modelin eğitim dönemi fiyatıyla (TÜFE endekslemesi
    ve oda payına bölme çağıranın işi). Backend'in yerel yolu ile Lambda
    servisi aynı fonksiyonu çağırır; eşlik testi
    (services/fairprice/parity_check.py) ikisinin aynı sayıyı verdiğini sınar.
    """
    frame = pd.DataFrame([{
        "room": row["room"],
        "living room": row["living_room"],
        "area (m2)": row["area"],
        "age": row["age"],
        "floor": row["floor"],
        "district": str(row["district"]).strip(),
        # Boş dize = mahalle bilinmiyor; model ilçe genelinden tahmin eder.
        "neighborhood": str(row.get("neighborhood") or "").strip(),
    } for row in rows])
    features = build_features(frame, model["categories"])
    columns = [np.exp(m.predict(features)) for m in model["models"].values()]
    # Çeyreklik modelleri bağımsız eğitildiği için nadiren sıra bozulabilir.
    return [tuple(sorted(float(v) for v in values)) for values in zip(*columns)]
