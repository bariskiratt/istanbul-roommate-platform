"""AWS Lambda: adil kira bandı tahmin servisi.

POST /predict (API Gateway HTTP API, IAM yetkili; infra/service.tf)
    istek:  {"rows": [{"room": 2, "living_room": 1, "area": 90, "age": 20,
                       "floor": 3, "district": "Kadıköy",
                       "neighborhood": "Caferağa Mah."}, ...]}   en fazla 100 satır
    yanıt:  {"model_version": "...", "bands": [[low, mid, high], ...]}

Bant, backend'in yerel yolundakiyle AYNI fonksiyondan gelir
(backend/app/pricing.py: predict_band); dosya imaja kopyalanır, burada
yeniden yazılmaz. Bant ham daire kirasıdır (eğitim dönemi TL'si): TÜFE
endekslemesi ve oda payı backend'in işidir. Böylece servis yalnızca modeli
sunar, ürün kuralı değişince yeniden dağıtılması gerekmez.

Model soğuk başlangıçta (init aşamasında) bir kez S3'ten alınır ve ortam
yaşadıkça bellekte kalır. Az trafikte ortam birkaç dakikada geri alındığı için
EventBridge her 5 dakikada bir {"warmup": true} gönderir (infra/service.tf):
bir ortam hep sıcak kalır, backend'in 3 sn'lik bütçesi soğuk başlangıca harcanmaz. Hangi modelin alınacağı imaja derlenirken sabitlenir (MODEL_VERSION,
MODEL_SHA256; .github/workflows/aws-deploy.yml): bir Lambda sürümü her zaman
aynı modeli sunar ve geri almak, takma adı önceki sürüme çevirmekten ibarettir.

Yerelde ve CI'daki eşlik testinde MODEL_PATH ile diskteki model kullanılır.
"""

import base64
import hashlib
import io
import json
import math
import os
import time

import joblib
# Model dosyası LightGBM/scikit-learn nesneleri taşıyor; joblib.load onları
# ilk kullanımda içe aktarır. Burada aktarılınca bu süre init aşamasına düşer
# ve CloudWatch'ta "Init Duration" olarak ayrı görünür.
import lightgbm  # noqa: F401
import sklearn  # noqa: F401

from app.pricing import feature_signature, predict_band

MAX_ROWS = 100
MAX_TEXT = 80

# Akıl sağlığı sınırları, pricing.BOUNDS DEĞİL: backend'in yerel yolu bu
# aralıkların dışındaki ilanlara da (ör. "12+1") tahmin üretiyor; servis
# aynı girdiye 400 dönseydi iki yol farklı davranırdı. Burada yalnızca anlamsız
# girdi (negatif alan, sonsuz sayı) reddedilir.
LIMITS = {
    "room": (0, 50),
    "living_room": (0, 20),
    "area": (1, 100_000),
    "age": (0, 1_000),
    "floor": (-10, 200),
}

_model = None
_model_version = None


class BadRequest(ValueError):
    pass


def _log(**fields) -> None:
    # CloudWatch Logs Insights JSON satırlarını alan alan okur (docs/AWS.md).
    print(json.dumps(fields, ensure_ascii=False))


def _read_model_bytes() -> tuple[bytes, str]:
    path = os.getenv("MODEL_PATH")
    if path:
        with open(path, "rb") as f:
            return f.read(), os.getenv("MODEL_VERSION") or "local"

    import boto3  # Lambda çalışma zamanında hazır

    version = os.environ["MODEL_VERSION"]
    key = f"fair-price/{version}/fair_price_model.joblib"
    body = boto3.client("s3").get_object(Bucket=os.environ["MODEL_BUCKET"], Key=key)
    return body["Body"].read(), version


def _load_model():
    """Modeli bir kez yükler ve doğrular; sonraki çağrılar bellekten."""
    global _model, _model_version
    if _model is not None:
        return _model, _model_version, False

    started = time.perf_counter()
    data, version = _read_model_bytes()
    expected_sha = os.getenv("MODEL_SHA256")
    if expected_sha and hashlib.sha256(data).hexdigest() != expected_sha:
        raise RuntimeError(f"model {version}: sha256 imajdaki sabitle tutmuyor")
    model = joblib.load(io.BytesIO(data))
    if model.get("signature") != feature_signature():
        raise RuntimeError(
            f"model {version}: imza {model.get('signature')} bu koddaki "
            f"pricing.py ile ({feature_signature()}) eğitilmemiş"
        )
    _model, _model_version = model, version
    _log(event="model_loaded", model_version=version,
         ms=round((time.perf_counter() - started) * 1000, 1), bytes=len(data))
    return model, version, True


def _number(row: dict, field: str, index: int) -> float:
    value = row.get(field)
    low, high = LIMITS[field]
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise BadRequest(f"rows[{index}].{field}: {low}–{high} arası bir sayı olmalı")
    return value


def _text(row: dict, field: str, index: int, required: bool) -> str:
    value = row.get(field, "")
    if value is None and not required:
        value = ""
    if not isinstance(value, str) or len(value) > MAX_TEXT:
        raise BadRequest(f"rows[{index}].{field}: en fazla {MAX_TEXT} karakterlik metin olmalı")
    if required and not value.strip():
        raise BadRequest(f"rows[{index}].{field}: boş olamaz")
    return value


def parse_rows(payload) -> list[dict]:
    rows = payload.get("rows") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
        raise BadRequest(f"'rows' 1–{MAX_ROWS} satırlık bir liste olmalı")
    parsed = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BadRequest(f"rows[{i}] bir nesne olmalı")
        parsed.append({
            **{field: _number(row, field, i) for field in LIMITS},
            "district": _text(row, "district", i, required=True),
            "neighborhood": _text(row, "neighborhood", i, required=False),
        })
    return parsed


def _payload(event: dict):
    """API Gateway (HTTP API, yük biçimi 2.0) olayı ya da doğrudan çağrı."""
    if "body" not in event:
        return event  # `aws lambda invoke` ile duman testi: olay gövdenin kendisi
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise BadRequest("gövde JSON değil") from exc


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def _warmup() -> dict:
    """Zamanlanmış ısıtma çağrısı: modeli yükle (yüklü değilse), tahmin yapma."""
    try:
        _, version, cold = _load_model()
    except Exception as exc:
        _log(event="model_unavailable", error=f"{type(exc).__name__}: {exc}")
        return _response(503, {"error": "model yüklenemedi"})
    _log(event="warmup", model_version=version, cold=cold)
    return _response(200, {"warm": True, "model_version": version})


def handler(event, context):
    started = time.perf_counter()
    if isinstance(event, dict) and event.get("warmup"):
        return _warmup()
    try:
        rows = parse_rows(_payload(event))
    except BadRequest as exc:
        _log(event="bad_request", error=str(exc))
        return _response(400, {"error": str(exc)})

    try:
        model, version, cold = _load_model()
    except Exception as exc:  # S3, yetki, doğrulama: 503, ayrıntı yalnız logda
        _log(event="model_unavailable", error=f"{type(exc).__name__}: {exc}")
        return _response(503, {"error": "model yüklenemedi"})

    bands = predict_band(model, rows)
    _log(event="predict", model_version=version, rows=len(rows), cold=cold,
         ms=round((time.perf_counter() - started) * 1000, 1))
    return _response(200, {
        "model_version": version,
        # Yuvarlanmaz: JSON float'ları birebir taşır, eşlik testi tam eşitlik ister.
        "bands": [list(band) for band in bands],
    })


# Init aşamasında yükle: soğuk başlangıcın ağır kısmı ilk isteğe değil buraya
# düşer. Hata olursa ortam yine açılır; handler yeniden dener ve 503 döner
# (init'te fırlatılan bir hata API Gateway'de anlamsız bir 502 olurdu).
if os.getenv("MODEL_PATH") or os.getenv("MODEL_VERSION"):
    try:
        _load_model()
    except Exception as exc:
        _log(event="model_unavailable", phase="init", error=f"{type(exc).__name__}: {exc}")
