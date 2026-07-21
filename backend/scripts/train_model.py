"""Adil kira fiyatı modelini eğitir, karşılaştırır ve kaydeder.

Çalıştırma:  python -m scripts.train_model
Çıktı:       models/fair_price_model.joblib
"""

import warnings

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from xgboost import XGBRegressor

from app.config import MODEL_PATH
from app.pricing import (
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    build_features,
    extract_categories,
    load_clean_data,
)

warnings.filterwarnings("ignore", category=UserWarning)

SEED = 42
N_SPLITS = 5

# Adil fiyat "bandı" için alt/orta/üst çeyrek modelleri.
QUANTILES = {"low": 0.25, "mid": 0.5, "high": 0.75}


def metrics(y_true_log, y_pred_log):
    """Hataları log uzayında değil, kullanıcının gördüğü TL uzayında raporla."""
    actual = np.exp(y_true_log)
    predicted = np.exp(y_pred_log)
    error = np.abs(actual - predicted)
    ss_res = np.sum((actual - predicted) ** 2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    return {
        "MAE": error.mean(),
        "MedAE": np.median(error),
        "MedAPE%": np.median(error / actual) * 100,
        "R2": 1 - ss_res / ss_tot,
    }


def make_lgbm(objective="regression", alpha=None):
    params = dict(
        objective=objective,
        n_estimators=600,
        learning_rate=0.05,
        num_leaves=31,
        min_child_samples=20,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=SEED,
        verbose=-1,
    )
    if alpha is not None:
        params["alpha"] = alpha
    return lgb.LGBMRegressor(**params)


def make_xgb():
    return XGBRegressor(
        n_estimators=600,
        learning_rate=0.05,
        max_depth=6,
        min_child_weight=5,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=SEED,
        enable_categorical=True,
        tree_method="hist",
    )


def make_ridge():
    """Doğrusal referans: ağaç modelleri bunu geçemiyorsa bir sorun var demektir."""
    return make_pipeline(
        ColumnTransformer([
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]),
        Ridge(alpha=1.0),
    )


def cross_validate(name, factory, X, y, df):
    """K-fold CV. Her fold'da model sıfırdan kurulur (bilgi sızmasın)."""
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    oof = np.zeros(len(y))

    for train_idx, test_idx in kf.split(X):
        model = factory()
        X_tr = X.iloc[train_idx]
        X_te = X.iloc[test_idx]
        if name == "Ridge":
            # OneHotEncoder kategorik dtype yerine düz string bekliyor.
            X_tr = X_tr.assign(**{c: X_tr[c].astype(str) for c in CATEGORICAL_FEATURES})
            X_te = X_te.assign(**{c: X_te[c].astype(str) for c in CATEGORICAL_FEATURES})
        model.fit(X_tr, y.iloc[train_idx])
        oof[test_idx] = model.predict(X_te)

    return metrics(y.values, oof)


def baseline_metrics(X, y, df):
    """Aptal referans: mahallenin medyan kirası (yoksa ilçenin, o da yoksa genel).

    Model bunu anlamlı biçimde geçemiyorsa özelliklerin bir değeri yok demektir.
    """
    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    oof = np.zeros(len(y))

    for train_idx, test_idx in kf.split(X):
        train, test = df.iloc[train_idx], df.iloc[test_idx]
        by_neigh = train.groupby(["district", "neighborhood"])["price"].median()
        by_dist = train.groupby("district")["price"].median()
        overall = train["price"].median()

        preds = [
            by_neigh.get((r.district, r.neighborhood))
            or by_dist.get(r.district)
            or overall
            for r in test.itertuples()
        ]
        oof[test_idx] = np.log(np.array(preds, dtype=float))

    return metrics(y.values, oof)


def main():
    print("🔄 Veri hazırlanıyor...")
    df = load_clean_data()
    X = build_features(df)
    y = np.log(df["price"].astype(float))
    print(f"   {len(df)} ilan, {X['district'].nunique()} ilçe, "
          f"{X['neighborhood'].nunique()} mahalle")

    print(f"\n📊 {N_SPLITS}-kat çapraz doğrulama (hatalar TL cinsinden):\n")
    results = {"Baseline (mahalle medyanı)": baseline_metrics(X, y, df)}
    for name, factory in [
        ("Ridge", make_ridge),
        ("XGBoost", make_xgb),
        ("LightGBM", make_lgbm),
        # Serviste bu model kullanılıyor (bandın orta çeyreği), bu yüzden
        # raporlanan hata gerçekten kullanıcıya giden tahminin hatası olsun.
        ("LightGBM q50 (servis edilen)", lambda: make_lgbm("quantile", 0.5)),
    ]:
        results[name] = cross_validate(name, factory, X, y, df)

    table = pd.DataFrame(results).T
    print(table.to_string(float_format=lambda v: f"{v:,.2f}"))

    baseline_error = table.loc["Baseline (mahalle medyanı)", "MedAPE%"]
    served_error = table.loc["LightGBM q50 (servis edilen)", "MedAPE%"]
    best = table["MedAPE%"].idxmin()
    print(f"\n🏆 En düşük hata: {best} (%{table.loc[best, 'MedAPE%']:.1f})")
    print(f"📦 Servis edilen model: LightGBM q50 (%{served_error:.1f}), "
          f"referanstan {baseline_error - served_error:.1f} puan iyi.")
    print("   Not: Nokta doğruluğunda modeller birbirine çok yakın; LightGBM'i "
          "seçme sebebi çeyreklik regresyonuyla bir 'aralık' verebilmesi.")

    # Nihai modeller tüm veriyle eğitilir. Nokta tahmini yerine bir bant
    # sunuyoruz: kullanıcıya "adil aralık" göstermek tek sayıdan dürüst.
    print("\n🔧 Nihai modeller eğitiliyor (çeyreklikler)...")
    models = {}
    for label, alpha in QUANTILES.items():
        model = make_lgbm(objective="quantile", alpha=alpha)
        model.fit(X, y)
        models[label] = model
        print(f"   q{int(alpha * 100)} tamam")

    artifact = {
        "models": models,
        "categories": extract_categories(X),
        "cv_results": table.to_dict(),
        "served_model": "LightGBM q50",
        "served_medape": float(served_error),
        "baseline_medape": float(baseline_error),
        "n_samples": len(df),
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    print(f"\n💾 '{MODEL_PATH.relative_to(MODEL_PATH.parent.parent)}' kaydedildi.")

    # Örnek tahmin — makul mü diye gözle bak.
    print("\n🔍 Örnek: Kadıköy / Caferağa Mah., 2+1, 90 m², 20 yaş, 3. kat")
    sample = pd.DataFrame([{
        "room": 2, "living room": 1, "area (m2)": 90, "age": 20, "floor": 3,
        "district": "Kadıköy", "neighborhood": "Caferağa Mah.",
    }])
    Xs = build_features(sample, artifact["categories"])
    band = {k: float(np.exp(m.predict(Xs)[0])) for k, m in models.items()}
    print(f"   Adil aralık: {band['low']:,.0f} – {band['high']:,.0f} TL "
          f"(orta: {band['mid']:,.0f} TL)")


if __name__ == "__main__":
    main()
