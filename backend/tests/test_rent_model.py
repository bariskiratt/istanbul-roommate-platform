"""Adil fiyat bandının kaynağı: AWS Lambda, S3'teki model ve yerel yedek.

Gerçek model ve ağ yok: sahte bir model ve requests.post/S3 yerine geçen
sahte nesneler. Sınanan şey yönlendirme: Lambda cevap verirse onun bandı,
vermezse (hata, zaman aşımı, bozuk yanıt) yerel modelin bandı; S3'ten gelen
model yalnızca imzası ve sha256'sı tutarsa kullanılır.
"""

import hashlib
import io
import json

import joblib
import numpy as np
import pytest
import requests
from fastapi.testclient import TestClient

from app import rent_model
from app.fairprice import estimate_for_listing
from app.main import STATE, app
from app.pricing import feature_signature

URL = "https://abc123.execute-api.eu-north-1.amazonaws.com/predict"
ROW = {
    "room": 2,
    "living_room": 1,
    "area": 90.0,
    "age": 20,
    "floor": 3,
    "district": "Kadıköy",
    "neighborhood": "Caferağa Mah.",
}


class FlatQuantile:
    """Her satıra aynı kirayı (log uzayında) tahmin eden sahte çeyreklik modeli."""

    def __init__(self, rent):
        self.rent = rent

    def predict(self, features):
        return np.full(len(features), np.log(self.rent))


@pytest.fixture()
def fake_model(monkeypatch):
    model = {
        "models": {
            "low": FlatQuantile(20_000),
            "mid": FlatQuantile(24_000),
            "high": FlatQuantile(30_000),
        },
        "categories": {
            "district": ["Kadıköy"],
            "neighborhood": ["Caferağa Mah."],
        },
        "served_medape": 15.3,
    }
    monkeypatch.setitem(STATE, "model", model)
    return model


@pytest.fixture()
def remote_env(monkeypatch):
    monkeypatch.setenv("FAIRPRICE_URL", URL)
    monkeypatch.setenv("FAIRPRICE_AWS_ACCESS_KEY_ID", "AKIDEXAMPLE")
    monkeypatch.setenv("FAIRPRICE_AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG")


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        return self.payload


@pytest.fixture()
def lambda_calls(monkeypatch):
    """requests.post yerine geçer; yanıt sırası `responses` listesinden."""
    calls = []
    responses = []

    def fake_post(url, data, headers, timeout):
        calls.append({"url": url, "body": json.loads(data), "headers": headers,
                      "timeout": timeout})
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(rent_model.requests, "post", fake_post)
    return calls, responses


def remote_band(low=21_000.0, mid=25_000.0, high=31_000.0):
    return FakeResponse({"model_version": "v1", "bands": [[low, mid, high]]})


# ---------------------------------------------------------------------------
# Yönlendirme
# ---------------------------------------------------------------------------


def test_local_model_when_lambda_not_configured(fake_model, lambda_calls):
    bands, served_by = rent_model.bands(fake_model, [ROW])
    assert served_by == "local"
    assert bands == [pytest.approx((20_000, 24_000, 30_000))]
    assert lambda_calls[0] == []


def test_url_without_keys_stays_local(fake_model, lambda_calls, monkeypatch):
    monkeypatch.setenv("FAIRPRICE_URL", URL)
    assert not rent_model.remote_configured()
    assert rent_model.bands(fake_model, [ROW])[1] == "local"


def test_lambda_band_is_used_and_request_is_signed(fake_model, remote_env, lambda_calls):
    calls, responses = lambda_calls
    responses.append(remote_band())

    bands, served_by = rent_model.bands(fake_model, [ROW])

    assert served_by == "lambda"
    assert bands == [(21_000.0, 25_000.0, 31_000.0)]
    (call,) = calls
    assert call["url"] == URL
    # Sözleşme ham alanlardır, özellik matrisi değil (pricing.ROW_FIELDS).
    assert call["body"] == {"rows": [ROW]}
    # API Gateway rotası IAM ister: istek URL'deki bölge ve bu servis için
    # SigV4 imzalı.
    auth = call["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/")
    assert "/eu-north-1/execute-api/aws4_request" in auth
    assert "X-Amz-Date" in call["headers"]
    assert call["timeout"] == (rent_model.CONNECT_TIMEOUT, rent_model.DEFAULT_TIMEOUT)


def test_region_comes_from_url_unless_given(monkeypatch):
    monkeypatch.setenv("FAIRPRICE_URL", "https://x1.execute-api.ap-southeast-2.amazonaws.com/predict")
    assert rent_model._region() == "ap-southeast-2"
    monkeypatch.setenv("FAIRPRICE_AWS_REGION", "eu-west-1")
    assert rent_model._region() == "eu-west-1"
    monkeypatch.delenv("FAIRPRICE_AWS_REGION")
    monkeypatch.setenv("FAIRPRICE_URL", "https://tahmin.example.com/predict")
    assert rent_model._region() == rent_model.DEFAULT_REGION


@pytest.mark.parametrize(
    "failure",
    [
        requests.Timeout("read timed out"),
        requests.ConnectionError("dns"),
        FakeResponse({"message": "Forbidden"}, status=403),
        FakeResponse({"bands": []}),  # satır sayısı tutmuyor
        FakeResponse({"bands": [[30_000, 25_000, 20_000]]}),  # sırasız bant
        FakeResponse({"bands": [[0, 1, 2]]}),  # sıfır kira
        FakeResponse({"unexpected": True}),
    ],
)
def test_any_lambda_failure_falls_back_to_local(
    fake_model, remote_env, lambda_calls, failure
):
    lambda_calls[1].append(failure)
    bands, served_by = rent_model.bands(fake_model, [ROW])
    assert served_by == "local"
    assert bands == [pytest.approx((20_000, 24_000, 30_000))]


def test_breaker_opens_after_consecutive_failures(fake_model, remote_env, lambda_calls):
    calls, responses = lambda_calls
    responses.extend([requests.Timeout("cold start"), requests.Timeout("down")])

    # Tek bir zaman aşımı (soğuk başlangıç) kesiciyi açmaz.
    assert rent_model.bands(fake_model, [ROW])[1] == "local"
    assert rent_model.status({"source": "image", "version": None})["lambda"] == "on"

    # İkincisi açar: sonraki istekler Lambda'yı hiç denemez.
    assert rent_model.bands(fake_model, [ROW])[1] == "local"
    assert rent_model.status(None)["lambda"] == "fallback"
    assert rent_model.bands(fake_model, [ROW])[1] == "local"
    assert len(calls) == 2


def test_success_resets_failure_count(fake_model, remote_env, lambda_calls):
    calls, responses = lambda_calls
    responses.extend([
        requests.Timeout("cold start"),
        remote_band(),
        requests.Timeout("blip"),
        remote_band(),
    ])
    served = [rent_model.bands(fake_model, [ROW])[1] for _ in range(4)]
    assert served == ["local", "lambda", "local", "lambda"]
    assert rent_model.status(None)["lambda"] == "on"


def test_oversized_batch_is_computed_locally(fake_model, remote_env, lambda_calls):
    rows = [ROW] * (rent_model.MAX_REMOTE_ROWS + 1)
    bands, served_by = rent_model.bands(fake_model, rows)
    assert served_by == "local"
    assert len(bands) == len(rows)
    assert lambda_calls[0] == []


# ---------------------------------------------------------------------------
# Uçlar: /api/estimate ve ilan adil fiyatı Lambda bandını aynı biçimde işler
# ---------------------------------------------------------------------------


def test_estimate_endpoint_uses_lambda_band(fake_model, remote_env, lambda_calls, monkeypatch):
    monkeypatch.setattr("app.main.rent_index", lambda: (1.0, "2025-02"))
    lambda_calls[1].append(remote_band(20_000, 24_000, 30_000))

    res = TestClient(app).post("/api/estimate", json={
        "district": "Kadıköy",
        "neighborhood": "Caferağa Mah.",
        "room": 2,
        "living_room": 1,
        "area": 90,
        "age": 20,
        "floor": 3,
    })

    assert res.status_code == 200
    body = res.json()
    assert body["served_by"] == "lambda"
    assert (body["fair_low"], body["fair_mid"], body["fair_high"]) == (20_000, 24_000, 30_000)
    assert body["room_mid"] == 12_000  # 2 yatak odası
    assert body["known_neighborhood"] is True


def test_estimate_endpoint_survives_lambda_outage(fake_model, remote_env, lambda_calls, monkeypatch):
    monkeypatch.setattr("app.main.rent_index", lambda: (1.0, "2025-02"))
    lambda_calls[1].append(requests.ConnectionError("AWS down"))

    res = TestClient(app).post("/api/estimate", json={
        "district": "Kadıköy",
        "neighborhood": "Caferağa Mah.",
        "room": 2,
        "living_room": 1,
        "area": 90,
        "age": 20,
        "floor": 3,
    })

    assert res.status_code == 200
    assert res.json()["served_by"] == "local"
    assert res.json()["fair_mid"] == 24_000


def test_listing_estimate_indexes_lambda_band(fake_model, remote_env, lambda_calls, monkeypatch):
    monkeypatch.setattr("app.fairprice.rent_index", lambda: (2.0, "2026-09"))
    calls, responses = lambda_calls
    responses.append(remote_band(10_000, 12_000, 15_000))

    result = estimate_for_listing("Kadıköy", "2+1", 13_000, "Bilinmeyen Mah.")

    assert result["served_by"] == "lambda"
    # Endeksleme ve oda payı backend'de: Lambda ham daire bandı döndürür.
    assert (result["flat_low"], result["flat_mid"], result["flat_high"]) == (20_000, 24_000, 30_000)
    assert result["room_mid"] == 12_000
    assert result["verdict"] == "fair"
    # Tanınmayan mahalle Lambda'ya da boş gider: tahmin ilçe geneline dayanır.
    assert calls[0]["body"]["rows"][0]["neighborhood"] == ""
    assert result["district_level"] is True


# ---------------------------------------------------------------------------
# Modeli S3'ten yükleme
# ---------------------------------------------------------------------------


class FakeS3:
    def __init__(self, objects):
        self.objects = objects

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}


def s3_with_model(model, *, signature=None, sha256=None):
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    data = buffer.getvalue()
    latest = {
        "version": "20261026-193000-abc1234",
        "model_key": "fair-price/20261026-193000-abc1234/fair_price_model.joblib",
        "sha256": sha256 or hashlib.sha256(data).hexdigest(),
        "signature": signature or feature_signature(),
    }
    return FakeS3({
        rent_model.LATEST_KEY: json.dumps(latest).encode(),
        latest["model_key"]: data,
    })


def test_s3_model_is_loaded_when_checks_pass():
    s3 = s3_with_model({"signature": feature_signature(), "served_medape": 15.3})
    model, version = rent_model.load_from_s3("evdes-models", s3)
    assert version == "20261026-193000-abc1234"
    assert model["served_medape"] == 15.3


def test_s3_model_trained_on_other_code_is_rejected():
    s3 = s3_with_model({"signature": "0" * 16}, signature="0" * 16)
    with pytest.raises(rent_model.ModelRejected, match="imza"):
        rent_model.load_from_s3("evdes-models", s3)


def test_s3_model_with_wrong_checksum_is_rejected():
    s3 = s3_with_model({"signature": feature_signature()}, sha256="0" * 64)
    with pytest.raises(rent_model.ModelRejected, match="sha256"):
        rent_model.load_from_s3("evdes-models", s3)


def test_unreachable_bucket_falls_back_to_image_model(monkeypatch, tmp_path):
    path = tmp_path / "fair_price_model.joblib"
    joblib.dump({"served_medape": 15.3}, path)
    monkeypatch.setattr(rent_model, "MODEL_PATH", path)
    monkeypatch.setenv("FAIRPRICE_MODEL_BUCKET", "evdes-models")

    def unreachable(bucket, s3=None):
        raise ConnectionError("no route to s3")

    monkeypatch.setattr(rent_model, "load_from_s3", unreachable)
    model, info = rent_model.load_model()
    assert model == {"served_medape": 15.3}
    assert info == {"source": "image", "version": None}


def test_no_model_anywhere(monkeypatch, tmp_path):
    monkeypatch.setattr(rent_model, "MODEL_PATH", tmp_path / "missing.joblib")
    assert rent_model.load_model() == (None, {"source": "none", "version": None})
