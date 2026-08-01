"""Raporlama uçları: oluşturma, tekilleştirme ve yönetici erişimi."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

# config.ADMIN_EMAILS ortam değişkeninden okunur; testte listeden birini alıp
# yönetici hesabını onunla kuruyoruz ki kurulum farkı testi kırmasın.
ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]
USER_EMAIL = "ali@uni.edu.tr"


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


def _auth_headers(client, email=USER_EMAIL) -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _make_listing(client, headers) -> int:
    return client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de güneşli 2+1",
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": [],
            "rent": 18000,
            "room_count": "2+1",
        },
    ).json()["id"]


def test_sebep_listesi_aciktir(client):
    res = client.get("/api/reports/reasons")
    assert res.status_code == 200
    assert res.json() == [
        "spam",
        "dolandiricilik",
        "taciz",
        "uygunsuz_icerik",
        "sahte_ilan",
        "diger",
    ]


def test_rapor_giris_ister(client):
    res = client.post(
        "/api/reports",
        json={"target_type": "listing", "target_id": 1, "reason": "spam"},
    )
    assert res.status_code == 401


def test_rapor_olusturma(client):
    owner = _auth_headers(client, "veli@uni.edu.tr")
    listing_id = _make_listing(client, owner)
    reporter = _auth_headers(client)

    res = client.post(
        "/api/reports",
        headers=reporter,
        json={
            "target_type": "listing",
            "target_id": listing_id,
            "reason": "sahte_ilan",
            "note": "Fotoğraflar başka ilandan alınmış.",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["target_type"] == "listing"
    assert body["reason"] == "sahte_ilan"
    assert body["resolved"] is False
    assert body["resolution_note"] is None


def test_ayni_hedef_iki_kez_raporlanamaz(client):
    owner = _auth_headers(client, "veli@uni.edu.tr")
    listing_id = _make_listing(client, owner)
    reporter = _auth_headers(client)
    payload = {
        "target_type": "listing",
        "target_id": listing_id,
        "reason": "spam",
    }

    assert client.post(
        "/api/reports", headers=reporter, json=payload
    ).status_code == 201
    res = client.post("/api/reports", headers=reporter, json=payload)
    assert res.status_code == 409, res.text

    # Başka bir kullanıcı aynı hedefi raporlayabilir
    other = _auth_headers(client, "deniz@uni.edu.tr")
    assert client.post(
        "/api/reports", headers=other, json=payload
    ).status_code == 201


def test_gecersiz_sebep_ve_olmayan_hedef(client):
    headers = _auth_headers(client)
    assert client.post(
        "/api/reports",
        headers=headers,
        json={"target_type": "listing", "target_id": 1, "reason": "kotu_koku"},
    ).status_code == 422
    assert client.post(
        "/api/reports",
        headers=headers,
        json={"target_type": "listing", "target_id": 999, "reason": "spam"},
    ).status_code == 404


def test_kendini_raporlayamaz(client):
    headers = _auth_headers(client)
    me = client.get("/api/auth/me", headers=headers).json()["id"]
    res = client.post(
        "/api/reports",
        headers=headers,
        json={"target_type": "user", "target_id": me, "reason": "taciz"},
    )
    assert res.status_code == 400


def test_liste_ve_cozme_yalniz_admin(client):
    owner = _auth_headers(client, "veli@uni.edu.tr")
    listing_id = _make_listing(client, owner)
    reporter = _auth_headers(client)
    report_id = client.post(
        "/api/reports",
        headers=reporter,
        json={
            "target_type": "listing",
            "target_id": listing_id,
            "reason": "spam",
        },
    ).json()["id"]

    # Sıradan kullanıcı göremez / çözemez.
    # NOT: raporu çözme ucu /api/admin/reports/{id} altına taşındı
    # (bkz. app/admin.py); tek yönetici yüzeyi bırakıldı.
    assert client.get("/api/reports", headers=reporter).status_code == 403
    assert client.patch(
        f"/api/admin/reports/{report_id}", headers=reporter, json={"resolved": True}
    ).status_code == 403
    assert client.get("/api/reports").status_code == 401

    admin = _auth_headers(client, ADMIN_EMAIL)
    rows = client.get("/api/reports", headers=admin).json()
    assert [r["id"] for r in rows] == [report_id]

    res = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin,
        json={"resolved": True, "resolution_note": "İlan kaldırıldı."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["resolved"] is True
    assert res.json()["resolution_note"] == "İlan kaldırıldı."

    # resolved filtresi
    assert client.get(
        "/api/reports", headers=admin, params={"resolved": False}
    ).json() == []
    assert len(
        client.get("/api/reports", headers=admin, params={"resolved": True}).json()
    ) == 1


def test_yaris_durumunda_500_yerine_409(client, monkeypatch):
    """SELECT-sonra-INSERT yarışı 500 vermemeli.

    Eşzamanlı iki istekte ön kontrol ikisinde de "kayıt yok" der, ikinci INSERT
    tekillik kısıtına takılır. Ön kontrolü hep "yok" dedirterek bu yarışı
    taklit ediyoruz.
    """
    from app import reports

    owner = _auth_headers(client, "veli@uni.edu.tr")
    listing_id = _make_listing(client, owner)
    reporter = _auth_headers(client)
    payload = {
        "target_type": "listing",
        "target_id": listing_id,
        "reason": "spam",
    }
    assert client.post(
        "/api/reports", headers=reporter, json=payload
    ).status_code == 201

    monkeypatch.setattr(reports, "_existing_report", lambda *a, **k: False)
    res = client.post("/api/reports", headers=reporter, json=payload)
    assert res.status_code == 409, res.text
    assert res.json()["detail"] == "Bu içeriği zaten raporladın."


def test_olmayan_rapor_patch_404(client):
    admin = _auth_headers(client, ADMIN_EMAIL)
    assert client.patch(
        "/api/reports/999", headers=admin, json={"resolved": True}
    ).status_code == 404
