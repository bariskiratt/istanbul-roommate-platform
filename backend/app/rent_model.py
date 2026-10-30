"""Adil fiyat modeli: nereden yüklenir, bandı kim hesaplar.

İki AWS parçası var; ikisi de isteğe bağlı ve ikisi de bozulduğunda site
bugünkü gibi çalışır (mimari ve kurulum: docs/AWS.md).

1. MODEL KAYNAĞI. FAIRPRICE_MODEL_BUCKET tanımlıysa açılışta S3'teki
   fair-price/latest.json'un gösterdiği model indirilir. Model GitHub
   Actions'ta eğitilip kalite kapısından geçerek oraya konur
   (scripts/publish_model.py). İndirilen model iki kontrolden geçmeden
   kullanılmaz: baytların sha256'sı latest.json'dakiyle, modelin imzası da bu
   kodun pricing.feature_signature() değeriyle aynı olmalı (eğitim/servis
   kayması). Değişken yoksa, S3'e ulaşılamazsa ya da kontrol tutmazsa imajdaki
   models/fair_price_model.joblib yüklenir (Dockerfile'da eğitilir).

2. TAHMİN. FAIRPRICE_URL tanımlıysa bant AWS Lambda'daki tahmin servisinden
   (services/fairprice, API Gateway arkasında) istenir. İstek SigV4 ile
   imzalanır: API Gateway rotası IAM yetkisi ister, yani paylaşılan bir
   parola yoktur; anahtar yalnızca bu rotayı çağırıp model klasörünü okuyabilen
   bir IAM kullanıcısınındır (infra/render.tf). Hata, zaman aşımı ya da
   tutarsız yanıtta bant yerel modelle hesaplanır; kullanıcı farkı görmez.
   Art arda hatalarda servis bir süre hiç denenmez (devre kesici), böylece
   AWS çöktüğünde her istek zaman aşımını beklemez.

Yerel model her durumda bellekte durur: hem yedek, hem de kategori listesi
(locations.py) ve medyan sapma gibi tahmin dışı bilgilerin kaynağı.
"""

import hashlib
import io
import json
import math
import os
import re
import threading
import time

import joblib
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from app.config import MODEL_PATH
from app.pricing import feature_signature, predict_band

LATEST_KEY = "fair-price/latest.json"
DEFAULT_REGION = "us-east-2"  # infra/variables.tf ile aynı
# https://<api-id>.execute-api.<bölge>.amazonaws.com/predict
_URL_REGION = re.compile(r"\.execute-api\.([a-z0-9-]+)\.amazonaws\.com")

# Lambda tek istekte en fazla bu kadar satır kabul eder (services/fairprice).
MAX_REMOTE_ROWS = 100

# Soğuk başlangıç (imaj + pandas/LightGBM importu + modeli S3'ten alma) birkaç
# saniye sürebilir. Bütçeyi aşan istek yerel modelle cevaplanır; Lambda yine de
# ısınır ve sonraki istekler oradan gelir.
DEFAULT_TIMEOUT = 3.0
CONNECT_TIMEOUT = 1.0

# Devre kesici: bu kadar ARDIŞIK hatadan sonra servis COOLDOWN saniye denenmez.
# Tek bir soğuk başlangıç zaman aşımı kesiciyi açmasın diye eşik 1 değil.
FAILURE_THRESHOLD = 2
COOLDOWN_SECONDS = 60

_lock = threading.Lock()
_consecutive_failures = 0
_open_until = 0.0


class ModelRejected(Exception):
    """S3'teki model bu kodla kullanılamaz (imza ya da sha256 tutmadı)."""


class BadAnswer(Exception):
    """Lambda'nın cevabı kullanılamaz; kullanıcıya gitmez, yalnız loglanır."""


def _region() -> str:
    """Açıkça verilmişse o; yoksa FAIRPRICE_URL'deki bölge (kova da orada)."""
    explicit = os.getenv("FAIRPRICE_AWS_REGION", "").strip()
    if explicit:
        return explicit
    match = _URL_REGION.search(os.getenv("FAIRPRICE_URL", ""))
    return match.group(1) if match else DEFAULT_REGION


def _credentials() -> Credentials | None:
    key = os.getenv("FAIRPRICE_AWS_ACCESS_KEY_ID", "").strip()
    secret = os.getenv("FAIRPRICE_AWS_SECRET_ACCESS_KEY", "").strip()
    if not (key and secret):
        return None
    return Credentials(key, secret)


def _timeout() -> float:
    try:
        return max(0.1, float(os.getenv("FAIRPRICE_TIMEOUT", DEFAULT_TIMEOUT)))
    except ValueError:
        return DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# 1. Model kaynağı
# ---------------------------------------------------------------------------


def _s3_client():
    import boto3
    from botocore.config import Config as BotoConfig

    creds = _credentials()
    return boto3.client(
        "s3",
        region_name=_region(),
        # Anahtar yoksa boto3'ün varsayılan zinciri (yerelde `aws sso login`).
        aws_access_key_id=creds.access_key if creds else None,
        aws_secret_access_key=creds.secret_key if creds else None,
        config=BotoConfig(
            connect_timeout=3,
            read_timeout=15,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def load_from_s3(bucket: str, s3=None):
    """latest.json'daki modeli indirir ve doğrular: (model, sürüm)."""
    s3 = s3 or _s3_client()
    latest = json.loads(s3.get_object(Bucket=bucket, Key=LATEST_KEY)["Body"].read())
    expected = feature_signature()
    if latest["signature"] != expected:
        raise ModelRejected(
            f"{latest['version']} başka bir pricing.py/kütüphane sürümüyle eğitilmiş "
            f"(imza {latest['signature']}, bu kod {expected}); yeni model eğitilene "
            f"kadar imajdaki kullanılır"
        )
    data = s3.get_object(Bucket=bucket, Key=latest["model_key"])["Body"].read()
    if hashlib.sha256(data).hexdigest() != latest["sha256"]:
        raise ModelRejected(f"{latest['model_key']} sha256 tutmadı")
    # joblib (pickle) yüklemek kod çalıştırmak demektir: yalnızca imzası ve
    # özeti doğrulanmış, yalnızca CI rolünün yazabildiği kovadan gelen dosya.
    model = joblib.load(io.BytesIO(data))
    if model.get("signature") != expected:
        raise ModelRejected(f"{latest['model_key']} içindeki imza tutmadı")
    return model, latest["version"]


def load_model():
    """Açılışta bir kez çağrılır: (model ya da None, kaynak bilgisi)."""
    bucket = os.getenv("FAIRPRICE_MODEL_BUCKET", "").strip()
    if bucket:
        try:
            model, version = load_from_s3(bucket)
            return model, {"source": "s3", "version": version}
        except Exception as exc:  # ağ, yetki, eksik dosya, doğrulama
            print(f"⚠️  Adil fiyat modeli S3'ten alınamadı ({exc}); "
                  f"imajdaki model kullanılacak.")
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH), {"source": "image", "version": None}
    return None, {"source": "none", "version": None}


# ---------------------------------------------------------------------------
# 2. Tahmin
# ---------------------------------------------------------------------------


def remote_configured() -> bool:
    return bool(os.getenv("FAIRPRICE_URL", "").strip()) and _credentials() is not None


def _remote_bands(rows):
    url = os.environ["FAIRPRICE_URL"].strip()
    body = json.dumps({"rows": rows}).encode()
    request = AWSRequest(
        method="POST", url=url, data=body, headers={"Content-Type": "application/json"}
    )
    SigV4Auth(_credentials(), "execute-api", _region()).add_auth(request)
    response = requests.post(
        url,
        data=body,
        headers=dict(request.headers.items()),
        timeout=(CONNECT_TIMEOUT, _timeout()),
    )
    response.raise_for_status()
    bands = response.json()["bands"]
    if len(bands) != len(rows):
        raise BadAnswer(f"{len(rows)} satıra {len(bands)} bant döndü")
    result = []
    for band in bands:
        low, mid, high = (float(v) for v in band)
        if not (0 < low <= mid <= high and math.isfinite(high)):
            raise BadAnswer(f"geçersiz bant {band}")
        result.append((low, mid, high))
    return result


def _record(ok: bool, exc: Exception | None = None) -> None:
    global _consecutive_failures, _open_until
    with _lock:
        if ok:
            _consecutive_failures = 0
            return
        _consecutive_failures += 1
        opened = _consecutive_failures >= FAILURE_THRESHOLD
        if opened:
            _open_until = time.monotonic() + COOLDOWN_SECONDS
            _consecutive_failures = 0
    # Yanıt gövdesi yazılmaz: kişisel veri yok ama gereksiz uzun olabilir.
    print(f"⚠️  Lambda tahmin servisi: {type(exc).__name__}: {exc}; yerel model."
          + (f" {COOLDOWN_SECONDS} sn denenmeyecek." if opened else ""))


def bands(model, rows):
    """Satırlar için ham daire bandı: (bantlar, "lambda" | "local").

    Satırlar pricing.ROW_FIELDS anahtarlı sözlükler; bant pricing.predict_band
    ile aynı biçimde (endekslenmemiş, dairenin tamamı). Bloklayan bir ağ
    çağrısı yapabilir: async uçlardan run_in_threadpool ile çağır.
    """
    if (
        remote_configured()
        and len(rows) <= MAX_REMOTE_ROWS
        and time.monotonic() >= _open_until
    ):
        try:
            result = _remote_bands(rows)
        except Exception as exc:  # zaman aşımı, 4xx/5xx, bozuk yanıt
            _record(False, exc)
        else:
            _record(True)
            return result, "lambda"
    return predict_band(model, rows), "local"


def status(info: dict | None) -> dict:
    """/api/health için: hangi model yüklü, Lambda yolu açık mı."""
    info = info or {"source": "none", "version": None}
    if not remote_configured():
        remote = "off"
    elif time.monotonic() < _open_until:
        remote = "fallback"  # devre kesici açık, tahminler yerel
    else:
        remote = "on"
    return {
        "model_source": info["source"],
        "model_version": info["version"],
        "lambda": remote,
    }


def reset() -> None:
    """Testler için: devre kesici durumunu sıfırla."""
    global _consecutive_failures, _open_until
    with _lock:
        _consecutive_failures = 0
        _open_until = 0.0
