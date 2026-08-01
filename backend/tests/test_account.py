"""Hesap ayarları: şifre değiştirme ve hesap silme."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app

EMAIL = "ali@uni.edu.tr"
PASSWORD = "Sifre1234"


@pytest.fixture()
def ctx():
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
    yield TestClient(app), TestSession
    app.dependency_overrides.clear()


def _login(client) -> dict:
    res = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    token = client.post(
        "/api/auth/verify-otp",
        json={"email": EMAIL, "code": res.json()["dev_code"]},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_change_password_flow(ctx):
    client, _ = ctx
    headers = _login(client)

    # Yanlış mevcut şifre reddedilir
    assert client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "Yanlis123", "new_password": "YeniSifre1"},
    ).status_code == 400

    # Aynı şifreye değiştirme reddedilir
    assert client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    ).status_code == 400

    # Doğru akış
    assert client.post(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "YeniSifre1"},
    ).status_code == 204

    # Eski token düşer, eski şifre çalışmaz, yenisi çalışır
    assert client.get("/api/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": "YeniSifre1"}
    ).status_code == 200


def test_delete_account_removes_everything(ctx):
    client, TestSession = ctx
    headers = _login(client)
    client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Silinecek ilan",
            "description": "test",
            "district": "Kadıköy",
            "photos": [],
            "rent": 10000,
            "room_count": "2+1",
        },
    )

    # Yanlış şifreyle silinemez
    assert client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": "Yanlis123"}
    ).status_code == 400

    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": PASSWORD}
    )
    assert res.status_code == 204

    # Kullanıcı, token ve ilanı gitti
    with TestSession() as db:
        assert db.scalar(select(models.User).where(models.User.email == EMAIL)) is None
        assert db.scalars(select(models.Listing)).all() == []
        assert db.scalars(select(models.AuthToken)).all() == []
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def _register(client, email: str) -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    )
    token = client.post(
        "/api/auth/verify-otp",
        json={"email": email, "code": res.json()["dev_code"]},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _make_listing(client, headers, title="Kadıköy'de 2+1") -> int:
    return client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": title,
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": [],
            "rent": 18000,
            "room_count": "2+1",
        },
    ).json()["id"]


def test_rapor_gondermis_kullanici_hesabini_silebilir(ctx):
    """Report.reporter_id users.id'ye FK ile bağlı.

    Raporlar temizlenmezse üretimdeki Postgres kısıtı hesabın silinmesini
    engeller ve uç 500 döner. (conftest SQLite'ta da FK'yı açıyor, bu yüzden
    test üretimdeki davranışı görüyor.)
    """
    client, TestSession = ctx
    veli = _register(client, "veli@uni.edu.tr")
    listing_id = _make_listing(client, veli)

    ali = _login(client)  # EMAIL ile kayıt olur
    ali_id = client.get("/api/auth/me", headers=ali).json()["id"]
    assert client.post(
        "/api/reports",
        headers=ali,
        json={
            "target_type": "listing",
            "target_id": listing_id,
            "reason": "sahte_ilan",
        },
    ).status_code == 201

    # Ali'yi hedef alan bir rapor da olsun (target_id'de FK yok, ama hedef
    # silinince incelenecek bir şey kalmadığı için temizlenmeli)
    assert client.post(
        "/api/reports",
        headers=veli,
        json={"target_type": "user", "target_id": ali_id, "reason": "taciz"},
    ).status_code == 201

    res = client.request(
        "DELETE", "/api/auth/me", headers=ali, json={"password": PASSWORD}
    )
    assert res.status_code == 204, res.text

    with TestSession() as db:
        assert db.scalar(select(models.User).where(models.User.email == EMAIL)) is None
        # Ne gönderdiği ne de hedefi olduğu rapor kaldı
        assert db.scalars(select(models.Report)).all() == []


def test_hesap_silmek_raporlanan_ilani_ve_mesaji_da_temizler(ctx):
    """Silinen kullanıcının ilanına açılmış rapor arkada kalmamalı."""
    client, TestSession = ctx
    ali = _login(client)
    listing_id = _make_listing(client, ali, "Ali'nin evi")

    veli = _register(client, "veli@uni.edu.tr")
    assert client.post(
        "/api/reports",
        headers=veli,
        json={"target_type": "listing", "target_id": listing_id, "reason": "spam"},
    ).status_code == 201

    assert client.request(
        "DELETE", "/api/auth/me", headers=ali, json={"password": PASSWORD}
    ).status_code == 204

    with TestSession() as db:
        assert db.scalars(select(models.Report)).all() == []
        # Raporu gönderen kullanıcı silinmedi
        assert db.scalar(
            select(models.User).where(models.User.email == "veli@uni.edu.tr")
        ) is not None
