"""/api/health: dağıtım sonrası veritabanı ve fotoğraf deposu doğrulaması."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import uploads as uploads_module
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def client():
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


@pytest.fixture()
def bucket_env(monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "roommatch-photos")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://hesap.r2.cloudflarestorage.com")


def test_disk_mode_is_healthy(client, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"database": "ok", "photo_storage": "disk"}


def test_bucket_reports_startup_check(client, bucket_env, monkeypatch):
    # Açılış sınaması henüz bitmediyse sağlıklı sayılır ama durum görünür.
    monkeypatch.setattr(uploads_module, "_bucket_check", "unchecked")
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {
        "database": "ok",
        "photo_storage": "bucket",
        "photo_bucket": "unchecked",
    }

    monkeypatch.setattr(uploads_module, "_bucket_check", "ok")
    assert client.get("/api/health").json()["photo_bucket"] == "ok"


def test_failed_bucket_check_is_503(client, bucket_env, monkeypatch):
    monkeypatch.setattr(uploads_module, "_bucket_check", "error")
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json()["photo_bucket"] == "error"


def test_database_failure_is_503_without_details(client, monkeypatch):
    monkeypatch.delenv("S3_BUCKET", raising=False)

    class BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("password authentication failed for user x")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    res = client.get("/api/health")
    assert res.status_code == 503
    assert res.json() == {"database": "error", "photo_storage": "disk"}
    assert "password" not in res.text
