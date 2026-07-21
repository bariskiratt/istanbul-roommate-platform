"""Ham ilan verisinden mahalle bazlı piyasa değerlerini üretir.

Çalıştırma: python -m scripts.build_market_values
Çıktı: data/processed/neighborhood_market_values.csv (API'nin ısı haritasını
renklendirmek için kullandığı dosya).
"""

import pandas as pd

from app.config import LISTINGS_CSV, MARKET_VALUES_CSV

# Ham veri seti kirli: "price" sütununda aylık kira (~22.000 TL medyan) ile
# birlikte satılık ilan fiyatları (23.000.000 TL'ye kadar) ve bin cinsinden
# girilmiş değerler (40, 60 gibi) karışık duruyor. Bu bant dışındaki her şeyi
# kira olarak kabul etmiyoruz.
MIN_RENT = 3_000
MAX_RENT = 500_000

# Tek bir ilandan mahalle ortalaması üretmek yanıltıcı olur.
MIN_LISTINGS = 3


def build_market_values(file_path=LISTINGS_CSV, output_path=MARKET_VALUES_CSV):
    print("🔄 Veri seti yükleniyor...")
    df = pd.read_csv(file_path)

    df["district"] = df["district"].astype(str).str.strip()
    df["neighborhood"] = df["neighborhood"].astype(str).str.strip()
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

    before = len(df)
    df = df.drop_duplicates()
    print(f"🧹 {before - len(df)} yinelenen kayıt silindi.")

    # Geçerli kira bandı ve pozitif metrekare filtresi.
    df = df[
        df["price"].between(MIN_RENT, MAX_RENT)
        & (df["area (m2)"] > 0)
    ].copy()
    print(f"🧹 Kira bandı ({MIN_RENT:,}-{MAX_RENT:,} TL) dışındaki ilanlar elendi, "
          f"{len(df)} kayıt kaldı.")

    df["price_per_m2"] = df["price"] / df["area (m2)"]

    # Medyan kullanıyoruz: ortalama, tek bir aşırı ilandan ciddi şekilde etkilenir.
    summary = (
        df.groupby(["district", "neighborhood"])
        .agg(
            total_listings=("price", "count"),
            avg_price=("price", "median"),
            avg_price_per_m2=("price_per_m2", "median"),
        )
        .reset_index()
    )

    dropped = summary[summary["total_listings"] < MIN_LISTINGS]
    summary = summary[summary["total_listings"] >= MIN_LISTINGS]
    print(f"🧹 {len(dropped)} mahalle {MIN_LISTINGS} ilandan az olduğu için elendi.")

    summary = summary.sort_values("avg_price", ascending=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print(f"\n📍 En pahalı 10 mahalle:")
    print(summary.head(10).to_string(index=False))
    print(f"\n💾 {len(summary)} mahalle '{output_path}' dosyasına yazıldı.")
    return summary


if __name__ == "__main__":
    try:
        build_market_values()
    except FileNotFoundError:
        print(f"❌ Hata: '{LISTINGS_CSV}' bulunamadı.")
