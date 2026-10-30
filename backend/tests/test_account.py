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
            "photos": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"],
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
            "photos": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"],
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


# ---- şifresini unutan kullanıcı (rakip raporu #4) ----

NEW_PASSWORD = "YeniSifre1"


def _request_code(client, email: str = EMAIL) -> str:
    return client.post("/api/auth/request-otp", json={"email": email}).json()["dev_code"]


def test_sifre_kodla_sifirlanir_ve_tum_oturumlar_kapanir(ctx):
    client, _ = ctx
    old_headers = _login(client)

    code = _request_code(client)
    res = client.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == EMAIL

    # Eski oturum düştü, yeni oturum çalışıyor.
    assert client.get("/api/auth/me", headers=old_headers).status_code == 401
    new_headers = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200

    # Eski şifre geçmez, yenisi geçer; kod bir daha kullanılamaz.
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 401
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}
    ).status_code == 200
    assert client.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": code, "new_password": "BaskaSifre1"},
    ).status_code == 400


def test_sifre_sifirlama_yanlis_kod_ve_kisa_sifre(ctx):
    client, _ = ctx
    _login(client)
    code = _request_code(client)
    wrong = "000000" if code != "000000" else "111111"

    assert client.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": wrong, "new_password": NEW_PASSWORD},
    ).status_code == 400
    assert client.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": code, "new_password": "kisa"},
    ).status_code == 422
    # Kayıtlı olmayan adres: kod istenmemiş gibi davranılır.
    assert client.post(
        "/api/auth/reset-password",
        json={"email": "yok@uni.edu.tr", "code": code, "new_password": NEW_PASSWORD},
    ).status_code == 400
    # Şifre değişmedi.
    assert client.post(
        "/api/auth/login", json={"email": EMAIL, "password": PASSWORD}
    ).status_code == 200


def test_sifre_sifirlama_giris_koduyla_ayni_tahmin_kovasini_kullanir(ctx):
    """Ayrı kova olsaydı 6 haneli kod için uç başına ayrı 5 hak doğardı."""
    client, _ = ctx
    _login(client)
    code = _request_code(client)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/api/auth/verify-otp", json={"email": EMAIL, "code": wrong})
    res = client.post(
        "/api/auth/reset-password",
        json={"email": EMAIL, "code": code, "new_password": NEW_PASSWORD},
    )
    assert res.status_code == 429


def test_yonetici_sifresi_kodla_sifirlanamaz(ctx):
    """Yönetici girişi şifre + kod ister; kodla şifre koymak ikisini birden verirdi."""
    client, _ = ctx
    admin = "yonetici@uni.edu.tr"
    reg = client.post("/api/auth/register", json={"email": admin, "password": PASSWORD})
    client.post(
        "/api/auth/verify-otp",
        json={"email": admin, "code": reg.json()["dev_code"], "password": PASSWORD},
    )
    code = _request_code(client, admin)
    res = client.post(
        "/api/auth/reset-password",
        json={"email": admin, "code": code, "new_password": NEW_PASSWORD},
    )
    assert res.status_code == 403
    # Eski şifre hâlâ geçerli (ikinci adıma geçer).
    assert client.post(
        "/api/auth/login", json={"email": admin, "password": PASSWORD}
    ).json().get("otp_required") is True


def test_hesap_sifresiz_e_posta_koduyla_silinir(ctx):
    client, TestSession = ctx
    headers = _login(client)

    # Ne şifre ne kod: 422.
    assert client.request(
        "DELETE", "/api/auth/me", headers=headers, json={}
    ).status_code == 422

    code = _request_code(client)
    wrong = "000000" if code != "000000" else "111111"
    assert client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"code": wrong}
    ).status_code == 400

    assert client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"code": code}
    ).status_code == 204
    with TestSession() as db:
        assert db.scalar(select(models.User).where(models.User.email == EMAIL)) is None
