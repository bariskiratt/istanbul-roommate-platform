"""Fotoğraf yükleme testleri."""

import pytest
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
