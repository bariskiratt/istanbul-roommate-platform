"""Fotoğraf yükleme, servis ve silme testleri."""

import io

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import uploads as uploads_module
from app.db import Base, get_db
from app.main import app

# 1x1 PNG (geçerli imza yeterli; içerik doğrulaması content-type üzerinden)
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1e2d0000000049454e44ae426082"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Testler gerçek uploads klasörüne yazmasın
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", tmp_path)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth_headers(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": "ali@uni.edu.tr", "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_requires_auth(client):
    res = client.post(
        "/api/uploads", files={"file": ("a.png", PNG_BYTES, "image/png")}
    )
    assert res.status_code == 401


def test_upload_png_returns_absolute_url(client, tmp_path):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 201, res.text
    url = res.json()["url"]
    assert "/uploads/" in url and url.endswith(".png")
    # Dosya gerçekten yazıldı
    name = url.rsplit("/", 1)[-1]
    assert (tmp_path / name).read_bytes() == PNG_BYTES


def test_reject_wrong_type(client):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415


def test_reject_too_big(client, monkeypatch):
    monkeypatch.setattr(uploads_module, "MAX_BYTES", 10)
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 413


def test_reject_empty_file(client):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", b"", "image/png")},
    )
    assert res.status_code == 422


# --------------------------------------------------------------------------
# Servis ve silme — konteyner diski
# --------------------------------------------------------------------------


def _upload(client, headers) -> str:
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 201, res.text
    return res.json()["url"]


def test_disk_photo_is_served_with_cache_headers(client):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    res = client.get(f"/uploads/{name}")
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == uploads_module.PHOTO_CACHE_CONTROL


def test_only_our_name_pattern_is_served(client, tmp_path):
    # Dizinde olsa bile desen dışındaki bir dosya servis edilmez.
    (tmp_path / "notes.txt").write_text("gizli")
    assert client.get("/uploads/notes.txt").status_code == 404
    assert client.get(f"/uploads/{'a' * 32}.png").status_code == 404


def test_delete_removes_our_files_and_skips_others(client, tmp_path):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    deleted = uploads_module.delete_local_photos(
        [url, url, "https://images.unsplash.com/x.jpg", "/uploads/../app.db"]
    )
    assert deleted == 1
    assert not (tmp_path / name).exists()
    assert client.get(f"/uploads/{name}").status_code == 404


# --------------------------------------------------------------------------
# S3 uyumlu kova (Cloudflare R2) — S3_BUCKET tanımlıyken
# --------------------------------------------------------------------------


class FakeS3:
    """boto3 S3 istemcisinin bu modülün kullandığı dört çağrısı."""

    def __init__(self):
        self.objects: dict[tuple[str, str], dict] = {}
        self.fail_with: Exception | None = None

    def _check(self):
        if self.fail_with is not None:
            raise self.fail_with

    def put_object(self, Bucket, Key, Body, **kwargs):
        self._check()
        self.objects[(Bucket, Key)] = {"Body": Body, **kwargs}

    def get_object(self, Bucket, Key):
        self._check()
        if (Bucket, Key) not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "yok"}}, "GetObject"
            )
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["Body"])}

    def delete_object(self, Bucket, Key):
        self._check()
        self.objects.pop((Bucket, Key), None)


@pytest.fixture()
def bucket(monkeypatch):
    fake = FakeS3()
    monkeypatch.setenv("S3_BUCKET", "roommatch-photos")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://hesap.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "anahtar")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "gizli")
    monkeypatch.setattr(uploads_module, "_s3_client", lambda settings: fake)
    return fake


def test_bucket_settings_follow_env(bucket, monkeypatch):
    settings = uploads_module.bucket_settings()
    assert settings.bucket == "roommatch-photos"
    assert settings.endpoint_url == "https://hesap.r2.cloudflarestorage.com"
    assert settings.region == "auto"

    monkeypatch.delenv("S3_BUCKET")
    assert uploads_module.bucket_settings() is None


def test_upload_goes_to_bucket_not_disk(client, bucket, tmp_path):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    # URL biçimi değişmez: arayüz ve veritabanı depodan habersiz.
    assert "/uploads/" in url
    stored = bucket.objects[("roommatch-photos", f"uploads/{name}")]
    assert stored["Body"] == PNG_BYTES
    assert stored["ContentType"] == "image/png"
    assert list(tmp_path.iterdir()) == []


def test_bucket_photo_is_served_with_hardening_headers(client, bucket):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    res = client.get(f"/uploads/{name}")
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == uploads_module.PHOTO_CACHE_CONTROL
    # M4 başlıkları kovadan gelen yanıtta da var.
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"] == "attachment"


def test_missing_bucket_photo_is_404(client, bucket):
    assert client.get(f"/uploads/{'b' * 32}.jpg").status_code == 404


def test_bucket_outage_on_upload_is_503(client, bucket):
    headers = _auth_headers(client)
    bucket.fail_with = EndpointConnectionError(endpoint_url="https://r2.invalid")
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 503
    assert bucket.objects == {}


def test_bucket_outage_on_read_is_502(client, bucket):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]
    bucket.fail_with = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "hayır"}}, "GetObject"
    )
    assert client.get(f"/uploads/{name}").status_code == 502


def test_bucket_delete_never_raises(client, bucket):
    url = _upload(client, _auth_headers(client))
    bucket.fail_with = EndpointConnectionError(endpoint_url="https://r2.invalid")
    # Hesap silme bu yüzden 500 vermemeli: hata yutulur, sayı 0 döner.
    assert uploads_module.delete_local_photos([url]) == 0


def test_account_deletion_removes_photos_from_bucket(client, bucket):
    headers = _auth_headers(client)
    photos = [_upload(client, headers) for _ in range(3)]
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de 2+1",
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": photos,
            "rent": 18000,
            "room_count": "2+1",
        },
    )
    assert res.status_code == 201, res.text
    assert len(bucket.objects) == 3

    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": "Sifre1234"}
    )
    assert res.status_code == 204
    assert bucket.objects == {}
