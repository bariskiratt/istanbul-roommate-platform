"""Adil fiyat modeli için ortak veri hazırlama.

Eğitim (`train_model.py`) ve servis (`main.py`) aynı dönüşümleri kullanmalı,
yoksa modele eğitimdekinden farklı dağılımlı veri gider. Bu yüzden tüm
temizlik ve özellik üretimi tek yerde tutuluyor.
"""

import numpy as np
import pandas as pd

from app.config import LISTINGS_CSV, MODEL_PATH  # noqa: F401  (MODEL_PATH yeniden ihraç)

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
        dtype = (
            pd.CategoricalDtype(categories[column])
            if categories is not None
            else pd.CategoricalDtype(sorted(values.unique()))
        )
        X[column] = values.astype(dtype)

    return X[FEATURES]


def extract_categories(X):
    """Eğitimde kullanılan kategori listelerini çıkarır (serviste yeniden kullanmak için)."""
    return {c: list(X[c].cat.categories) for c in CATEGORICAL_FEATURES}
