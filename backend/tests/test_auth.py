"""Kayıt → OTP doğrulama → me/profil → ilan sahipliği → çıkış akışı."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

REGISTER = {"email": "Ali@Uni.EDU.tr", "password": "Sifre1234"}


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


def _register_and_login(client) -> tuple[str, dict]:
    res = client.post("/api/auth/register", json=REGISTER)
    assert res.status_code == 201, res.text
    code = res.json()["dev_code"]

    res = client.post(
        "/api/auth/verify-otp",
        json={"email": REGISTER["email"], "code": code},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    return body["token"], body["user"]


def test_register_verify_me(client):
    token, user = _register_and_login(client)
    assert user["email"] == "ali@uni.edu.tr"  # normalize edildi
    assert user["verified"] is True

    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["id"] == user["id"]


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401
    res = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer gecersiz-token"}
    )
    assert res.status_code == 401


def test_duplicate_register_conflict(client):
    _register_and_login(client)
    res = client.post("/api/auth/register", json=REGISTER)
    assert res.status_code == 409


def test_wrong_otp_rejected(client):
    client.post("/api/auth/register", json=REGISTER)
    res = client.post(
        "/api/auth/verify-otp",
        json={"email": REGISTER["email"], "code": "000000"},
    )
    # 1/1.000.000 ihtimalle gerçek kod 000000 olabilir; test sabit tohum
    # kullanmadığından bu riski kabul ediyoruz.
    assert res.status_code == 400


def test_request_otp_unknown_email(client):
    res = client.post("/api/auth/request-otp", json={"email": "yok@uni.edu.tr"})
    assert res.status_code == 404


def test_profile_update(client):
    token, _ = _register_and_login(client)
    res = client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Ali", "university": "Sahte Üniv", "budget_min": 5000, "budget_max": 9000},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Ali"
    # Üniversite elle değiştirilemez: gönderilen değer yok sayılır
    # (uni.edu.tr eşlemede yok -> kayıtta None atanmıştı, öyle kalmalı)
    assert res.json()["university"] is None

    res = client.patch(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"budget_min": 9000, "budget_max": 5000},
    )
    assert res.status_code == 422


def test_listing_ownership_and_mine(client):
    token, user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    listing = {
        "type": "kisisel_ilan",
        "title": "Oda arıyorum",
        "description": "test",
        "district": "Kadıköy",
        "photos": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"],
        "budget_min": 5000,
        "budget_max": 9000,
    }
    res = client.post("/api/listings", json=listing, headers=headers)
    assert res.status_code == 201
    assert res.json()["owner_id"] == user["id"]

    # Token'sız ilan oluşturulamaz
    assert client.post("/api/listings", json=listing).status_code == 401

    # mine=true yalnızca kendi ilanını döndürür
    res = client.get("/api/listings", params={"mine": "true"}, headers=headers)
    assert [i["owner_id"] for i in res.json()] == [user["id"]]

    # mine token'sız 401
    assert client.get("/api/listings", params={"mine": "true"}).status_code == 401

    # Sahipli ilanı başkası (token'sız) kapatamaz
    owned_id = 1
    assert client.delete(f"/api/listings/{owned_id}").status_code == 401
    assert client.delete(f"/api/listings/{owned_id}", headers=headers).status_code == 204


def test_birth_year_age_limits(client):
    from datetime import datetime, timezone

    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    year = datetime.now(timezone.utc).year

    # 22 yaşında -> kabul
    ok = client.patch("/api/auth/me", headers=headers, json={"birth_year": year - 22})
    assert ok.status_code == 200

    # 15 ve 45 yaşında -> reddedilir
    assert client.patch(
        "/api/auth/me", headers=headers, json={"birth_year": year - 15}
    ).status_code == 422
    assert client.patch(
        "/api/auth/me", headers=headers, json={"birth_year": year - 45}
    ).status_code == 422


def test_password_login(client):
    _register_and_login(client)

    # Doğru şifre -> token
    res = client.post(
        "/api/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert res.status_code == 200, res.text
    token = res.json()["token"]
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 200

    # Yanlış şifre -> 401
    res = client.post(
        "/api/auth/login",
        json={"email": REGISTER["email"], "password": "YanlisSifre1"},
    )
    assert res.status_code == 401

    # Kayıtsız e-posta -> 401 (aynı mesaj; hesap varlığı sızdırılmaz)
    res = client.post(
        "/api/auth/login",
        json={"email": "yok@uni.edu.tr", "password": "Sifre1234"},
    )
    assert res.status_code == 401


def test_password_login_requires_verified(client):
    client.post("/api/auth/register", json=REGISTER)  # OTP doğrulanmadı
    res = client.post(
        "/api/auth/login",
        json={"email": REGISTER["email"], "password": REGISTER["password"]},
    )
    assert res.status_code == 403


def test_otp_brute_force_rate_limited(client):
    client.post("/api/auth/register", json=REGISTER)
    # 5 deneme hakkı; 6. istek 429 almalı (kod kaba kuvvetle denenemez)
    for _ in range(5):
        res = client.post(
            "/api/auth/verify-otp",
            json={"email": REGISTER["email"], "code": "000000"},
        )
        assert res.status_code in (400, 200)
    res = client.post(
        "/api/auth/verify-otp",
        json={"email": REGISTER["email"], "code": "000000"},
    )
    assert res.status_code == 429


def test_expired_token_rejected(client, monkeypatch):
    from datetime import timedelta

    from app import auth as auth_module

    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    # TTL'i sıfıra indir: aynı token artık geçersiz sayılmalı ve silinmeli
    monkeypatch.setattr(auth_module, "TOKEN_TTL", timedelta(seconds=-1))
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    # TTL normale dönse bile token silindiği için geçersiz kalır
    monkeypatch.setattr(auth_module, "TOKEN_TTL", timedelta(days=30))
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_logout_invalidates_token(client):
    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
