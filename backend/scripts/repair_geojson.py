"""Bozuk GeoJSON dosyasını onarır (tek seferlik yardımcı betik).

Çalıştırma: python -m scripts.repair_geojson
"""

from json_repair import repair_json

from app.config import NEIGHBORHOOD_GEOJSON, RAW_DIR

OUTPUT = RAW_DIR / "mahalle_fixed.geojson"

print("⏳ Dosya tamir ediliyor, lütfen bekle...")
fixed = repair_json(NEIGHBORHOOD_GEOJSON.read_text(encoding="utf-8"))
OUTPUT.write_text(fixed, encoding="utf-8")
print(f"✅ Tamamlandı! '{OUTPUT}' oluşturuldu.")