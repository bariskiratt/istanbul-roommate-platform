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
        json={"name": "Ali", "university": "İTÜ", "budget_min": 5000, "budget_max": 9000},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Ali"

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
        "photos": [],
        "budget_min": 5000,
        "budget_max": 9000,
    }
    res = client.post("/api/listings", json=listing, headers=headers)
    assert res.status_code == 201
    assert res.json()["owner_id"] == user["id"]

    # Anonim ilan (token'sız)
    res = client.post("/api/listings", json=listing)
    assert res.json()["owner_id"] is None

    # mine=true yalnızca kendi ilanını döndürür
    res = client.get("/api/listings", params={"mine": "true"}, headers=headers)
    assert [i["owner_id"] for i in res.json()] == [user["id"]]

    # mine token'sız 401
    assert client.get("/api/listings", params={"mine": "true"}).status_code == 401

    # Sahipli ilanı başkası (token'sız) kapatamaz
    owned_id = 1
    assert client.delete(f"/api/listings/{owned_id}").status_code == 403
    assert client.delete(f"/api/listings/{owned_id}", headers=headers).status_code == 204


def test_logout_invalidates_token(client):
    token, _ = _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401
