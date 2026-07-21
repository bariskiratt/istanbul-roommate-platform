import pandas as pd

from app.config import LISTINGS_CSV as CSV_PATH


def main():
    df = pd.read_csv(CSV_PATH)

    # Temel veri temizliği
    for column in df.select_dtypes(include=["object", "string"]):
        df[column] = df[column].astype(str).str.strip()

    # Aşırı büyük konfigürasyonları eleyelim:
    # - salon sayısı 5'ten büyük olanlar
    # - oda sayısı 11'den büyük olanlar
    original_count = len(df)
    df = df[
        (df["living room"] <= 5)
        & (df["room"] <= 11)
        & (df["floor"] <= 50)
        & (df["floor"] >= 0)
    ]
    print(f"\nFiltre uygulandı: {original_count - len(df)} kayıt elendi, "
          f"{len(df)} kayıt kaldı.")

    print("\n=== Veri Kümesi Hakkında Genel Bilgi ===")
    print(f"Satır sayısı: {df.shape[0]}")
    print(f"Sütun sayısı: {df.shape[1]}")
    print("Sütunlar:", ", ".join(df.columns))

    print("\n=== Veri Tipleri ve Eksik Değerler ===")
    print(df.dtypes)
    print("\nEksik değer sayıları:")
    print(df.isna().sum())

    print("\n=== İlk 10 Satır ===")
    print(df.head(10).to_string(index=False))

    print("\n=== Sayısal Sütunların Özet İstatistikleri ===")
    print(df.describe(include="all"))

    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    if numeric_columns:
        print("\n=== Sayısal Sütunlar ===")
        print(numeric_columns)

    print("\n=== Bölge Bazlı Kayıt Sayıları ===")
    for col in ["district", "neighborhood", "room", "living room", "floor"]:
        if col in df.columns:
            print(f"\n{col} dağılımı:")
            print(df[col].value_counts(dropna=False).head(15).to_string())

    if "price" in df.columns:
        print("\n=== Fiyat Dağılımı Özeti ===")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        print(df["price"].describe())

    if "area (m2)" in df.columns:
        print("\n=== Yaş ve Metrekare İlişkisi ===")
        print(df[["age", "area (m2)"]].corr())


if __name__ == "__main__":
    main()
