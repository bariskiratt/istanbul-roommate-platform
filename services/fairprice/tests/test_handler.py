"""AWS Lambda tahmin servisi (services/fairprice/handler.py)."""

import base64
import hashlib
import json

import joblib
import numpy as np
import pytest

import handler
import smoke_check
from app.pricing import feature_signature

ROW = {
    "room": 2,
    "living_room": 1,
    "area": 90,
    "age": 20,
    "floor": 3,
    "district": "Kadıköy",
    "neighborhood": "Caferağa Mah.",
}


class FlatQuantile:
    def __init__(self, rent):
        self.rent = rent

    def predict(self, features):
        return np.full(len(features), np.log(self.rent))


FAKE_MODEL = {
    "models": {
        "low": FlatQuantile(30_000),
        "mid": FlatQuantile(20_000),  # sırasız: servis yine sıralı döndürmeli
        "high": FlatQuantile(40_000),
    },
    "categories": {"district": ["Kadıköy"], "neighborhood": ["Caferağa Mah."]},
}


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(handler, "_model", None)
    monkeypatch.setattr(handler, "_model_version", None)
    for name in ("MODEL_PATH", "MODEL_VERSION", "MODEL_SHA256", "MODEL_BUCKET"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def loaded(monkeypatch):
    monkeypatch.setattr(handler, "_load_model", lambda: (FAKE_MODEL, "v1", False))


def api_event(body, *, encode=False):
    raw = json.dumps(body)
    return {
        "version": "2.0",
        "routeKey": "POST /predict",
        "isBase64Encoded": encode,
        "body": base64.b64encode(raw.encode()).decode() if encode else raw,
    }


def call(event):
    response = handler.handler(event, None)
    return response["statusCode"], json.loads(response["body"])


@pytest.mark.parametrize("encode", [False, True])
def test_predicts_sorted_raw_flat_band(loaded, encode):
    status, body = call(api_event({"rows": [ROW, {**ROW, "neighborhood": ""}]}, encode=encode))
    assert status == 200
    assert body["model_version"] == "v1"
    assert body["bands"] == [pytest.approx([20_000, 30_000, 40_000])] * 2


def test_direct_invoke_for_smoke_tests(loaded):
    status, body = call({"rows": [ROW]})
    assert status == 200 and len(body["bands"]) == 1


def test_neighborhood_is_optional(loaded):
    row = {k: v for k, v in ROW.items() if k != "neighborhood"}
    assert call(api_event({"rows": [row]}))[0] == 200


@pytest.mark.parametrize(
    "body, fragment",
    [
        ({}, "'rows'"),
        ({"rows": []}, "'rows'"),
        ({"rows": [ROW] * (handler.MAX_ROWS + 1)}, "'rows'"),
        ({"rows": ["x"]}, "rows[0]"),
        ({"rows": [{**ROW, "area": -5}]}, "rows[0].area"),
        ({"rows": [{**ROW, "room": True}]}, "rows[0].room"),
        ({"rows": [{**ROW, "age": "20"}]}, "rows[0].age"),
        ({"rows": [{**ROW, "district": "  "}]}, "rows[0].district"),
        ({"rows": [{**ROW, "neighborhood": "x" * 81}]}, "rows[0].neighborhood"),
    ],
)
def test_rejects_bad_input_with_400(loaded, body, fragment):
    status, payload = call(api_event(body))
    assert status == 400
    assert fragment in payload["error"]


def test_out_of_training_range_is_still_predicted(loaded):
    # Backend'in yerel yolu "12+1"e de tahmin üretir; servis 400 dönmemeli.
    assert call(api_event({"rows": [{**ROW, "room": 12}]}))[0] == 200


def test_non_json_body_is_400(loaded):
    event = api_event({})
    event["body"] = "not json"
    assert call(event)[0] == 400


def test_model_failure_is_503_without_details(monkeypatch):
    def broken():
        raise RuntimeError("AccessDenied for arn:aws:s3:::secret-bucket")

    monkeypatch.setattr(handler, "_load_model", broken)
    status, body = call(api_event({"rows": [ROW]}))
    assert status == 503
    assert "secret" not in json.dumps(body)


def test_warmup_loads_model_without_predicting(loaded):
    status, body = call({"warmup": True})
    assert status == 200
    assert body == {"warm": True, "model_version": "v1"}


# ---------------------------------------------------------------------------
# Modelin yüklenmesi ve doğrulanması
# ---------------------------------------------------------------------------


def write_model(tmp_path, monkeypatch, model):
    path = tmp_path / "fair_price_model.joblib"
    joblib.dump(model, path)
    monkeypatch.setenv("MODEL_PATH", str(path))
    monkeypatch.setenv("MODEL_VERSION", "v7")
    return path


def test_loads_model_once(tmp_path, monkeypatch):
    path = write_model(tmp_path, monkeypatch, {"signature": feature_signature()})
    monkeypatch.setenv("MODEL_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())

    model, version, cold = handler._load_model()
    assert version == "v7" and cold
    path.unlink()  # ikinci çağrı diske/S3'e gitmez
    assert handler._load_model() == (model, "v7", False)


def test_rejects_model_trained_with_other_code(tmp_path, monkeypatch):
    write_model(tmp_path, monkeypatch, {"signature": "0" * 16})
    with pytest.raises(RuntimeError, match="imza"):
        handler._load_model()


def test_rejects_model_that_does_not_match_pinned_hash(tmp_path, monkeypatch):
    write_model(tmp_path, monkeypatch, {"signature": feature_signature()})
    monkeypatch.setenv("MODEL_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="sha256"):
        handler._load_model()


# ---------------------------------------------------------------------------
# Dağıtım duman testi
# ---------------------------------------------------------------------------


def test_smoke_check_accepts_healthy_response(loaded):
    response = handler.handler(json.loads(smoke_check.EVENT.read_text()), None)
    assert smoke_check.check(response, "v1") == []


def test_smoke_check_rejects_wrong_model_and_errors(loaded):
    response = handler.handler(json.loads(smoke_check.EVENT.read_text()), None)
    assert "beklenen v2" in smoke_check.check(response, "v2")[0]
    assert smoke_check.check({"statusCode": 503, "body": "{}"}, "v1")
