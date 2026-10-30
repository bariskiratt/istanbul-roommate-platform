"""Modelin S3'e yüklenmesi ve kalite kapısı (scripts/publish_model.py)."""

import io
import json

import pytest
from botocore.exceptions import ClientError

from scripts import publish_model

GOOD = {
    "signature": "3132a18ebb9f4aa1",
    "sha256": "ab" * 32,
    "served_medape": 15.31,
    "band_coverage": 0.40,
    "n_samples": 8325,
    "git_commit": "91d820c",
}


def test_gate_passes_first_model():
    assert publish_model.gate(GOOD, None) == []


def test_gate_tolerates_retraining_noise():
    current = {**GOOD, "served_medape": 15.0}
    assert publish_model.gate({**GOOD, "served_medape": 15.4}, current) == []


def test_gate_rejects_worse_model():
    current = {**GOOD, "served_medape": 15.0}
    (reason,) = publish_model.gate({**GOOD, "served_medape": 16.1}, current)
    assert "medyan sapma" in reason


@pytest.mark.parametrize("coverage", [0.1, 0.9])
def test_gate_rejects_collapsed_or_useless_band(coverage):
    (reason,) = publish_model.gate({**GOOD, "band_coverage": coverage}, None)
    assert "kapsama" in reason


def test_gate_rejects_truncated_data():
    (reason,) = publish_model.gate({**GOOD, "n_samples": 900}, None)
    assert "satır" in reason


class FakeS3:
    """Yalnızca publish()'in kullandığı çağrılar."""

    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self, objects=None):
        self.objects = dict(objects or {})

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **_kwargs):
        self.objects[Key] = Body

    def upload_file(self, filename, Bucket, Key):
        with open(filename, "rb") as f:
            self.objects[Key] = f.read()


@pytest.fixture()
def trained(tmp_path, monkeypatch):
    model = tmp_path / "fair_price_model.joblib"
    model.write_bytes(b"model-bytes")
    metrics = tmp_path / "metrics.json"
    monkeypatch.setattr(publish_model, "MODEL_PATH", model)
    monkeypatch.setattr(publish_model, "MODEL_METRICS_PATH", metrics)

    def write(**overrides):
        metrics.write_text(json.dumps({**GOOD, **overrides}))

    write()
    return write


def latest(s3):
    return json.loads(s3.objects[publish_model.LATEST_KEY])


def test_first_model_is_uploaded_and_promoted(trained):
    s3 = FakeS3()
    promoted, reasons, record = publish_model.publish(s3, "bucket", "v1")
    assert promoted and reasons == []
    assert s3.objects["fair-price/v1/fair_price_model.joblib"] == b"model-bytes"
    assert json.loads(s3.objects["fair-price/v1/metrics.json"])["sha256"] == GOOD["sha256"]
    assert latest(s3)["version"] == "v1"
    assert latest(s3)["previous_version"] is None
    assert record["signature"] == GOOD["signature"]


def test_rejected_model_is_kept_but_not_promoted(trained):
    s3 = FakeS3()
    publish_model.publish(s3, "bucket", "v1")
    trained(served_medape=17.0)

    promoted, reasons, _ = publish_model.publish(s3, "bucket", "v2")

    assert not promoted and reasons
    # Aday yine de kendi klasöründe: neden reddedildiğine sonradan bakılabilir.
    assert "fair-price/v2/metrics.json" in s3.objects
    assert latest(s3)["version"] == "v1"


def test_better_model_replaces_latest(trained):
    s3 = FakeS3()
    publish_model.publish(s3, "bucket", "v1")
    trained(served_medape=15.0)
    promoted, _, _ = publish_model.publish(s3, "bucket", "v2")
    assert promoted
    assert latest(s3)["version"] == "v2"
    assert latest(s3)["previous_version"] == "v1"


def test_version_folders_are_immutable(trained):
    s3 = FakeS3()
    publish_model.publish(s3, "bucket", "v1")
    with pytest.raises(SystemExit, match="zaten var"):
        publish_model.publish(s3, "bucket", "v1")
