"""Eşlik testi: Lambda imajı, backend'in yerel modeliyle AYNI bandı veriyor mu?

CI'da (.github/workflows/aws-checks.yml) imaj, AWS'siz, Lambda'nın kendi
çalışma zamanı öykünücüsüyle (Runtime Interface Emulator, taban imajda hazır)
ayağa kaldırılır ve eğitilmiş model içine bağlanır. Bu betik aynı modelle
200 rastgele ilanı hem yerelde (backend/app/pricing.py) hem imajda tahmin eder
ve sonuçları karşılaştırır. Bağımlılık sürümleri ya da özellik üretimi iki
tarafta ayrışırsa sayılar ayrışır ve CI kırmızı olur.

    python services/fairprice/parity_check.py \
        --model backend/models/fair_price_model.joblib \
        --endpoint http://localhost:9000/2015-03-31/functions/function/invocations
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.pricing import BOUNDS, predict_band  # noqa: E402

# Bitwise aynı kütüphane sürümleri aynı sayıyı verir; tolerans yalnızca
# JSON'un float gidiş-dönüşü için (pratikte 0 çıkıyor).
TOLERANCE = 1e-9


def random_rows(model, count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    districts = model["categories"]["district"]
    neighborhoods = model["categories"]["neighborhood"]
    rows = []
    for i in range(count):
        rows.append({
            "room": rng.randint(*BOUNDS["room"]),
            "living_room": rng.randint(0, 2),
            "area": round(rng.uniform(*BOUNDS["area (m2)"]), 1),
            "age": rng.randint(*BOUNDS["age"]),
            "floor": rng.randint(*BOUNDS["floor"]),
            "district": rng.choice(districts),
            # Her beşinci satırda mahalle bilinmiyor ya da modelin tanımadığı
            # bir ad: ilçe geneline düşen yol da sınansın.
            "neighborhood": (
                rng.choice(["", "Olmayan Mah."]) if i % 5 == 0 else rng.choice(neighborhoods)
            ),
        })
    return rows


def invoke(endpoint: str, rows: list[dict]) -> dict:
    # API Gateway HTTP API'nin (yük biçimi 2.0) Lambda'ya ilettiği olayın özü.
    event = {
        "version": "2.0",
        "routeKey": "POST /predict",
        "rawPath": "/predict",
        "isBase64Encoded": False,
        "body": json.dumps({"rows": rows}),
    }
    request = urllib.request.Request(
        endpoint, data=json.dumps(event).encode(), method="POST",
        headers={"Content-Type": "application/json"},
    )
    # Konteyner yeni açıldıysa öykünücü birkaç saniye bağlantı kabul etmez.
    for attempt in range(30):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except ConnectionError:
            time.sleep(1)
        except urllib.error.URLError as exc:
            if not isinstance(exc.reason, ConnectionError):
                raise
            time.sleep(1)
    raise SystemExit(f"{endpoint} 30 saniyede açılmadı")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    model = joblib.load(args.model)
    rows = random_rows(model, args.count, args.seed)
    expected = predict_band(model, rows)

    received, timings = [], []
    for start in range(0, len(rows), 50):
        began = time.perf_counter()
        result = invoke(args.endpoint, rows[start:start + 50])
        timings.append((time.perf_counter() - began) * 1000)
        if result.get("statusCode") != 200:
            print(f"❌ Lambda {result.get('statusCode')}: {result.get('body')}")
            return 1
        received.extend(json.loads(result["body"])["bands"])

    worst = max(
        abs(got - want) / want
        for got_band, want_band in zip(received, expected)
        for got, want in zip(got_band, want_band)
    )
    print(f"{len(rows)} ilan · en büyük göreli fark {worst:.2e} · "
          f"çağrı süreleri (ms): {', '.join(f'{t:.0f}' for t in timings)} "
          f"(ilki soğuk başlangıç)")
    if len(received) != len(expected) or worst > TOLERANCE:
        print("❌ Lambda ile yerel model farklı bant veriyor.")
        return 1
    print("✅ Lambda ile yerel model aynı bandı veriyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
