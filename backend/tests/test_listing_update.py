"""PATCH /api/listings/{id} — denetim yalnızca metin değişince koşar.

Denetim kuralları ilan yayımlandıktan sonra sıkılaşabilir. Eski metni bugünün
kurallarına takılan bir ilanın sahibi, metne hiç dokunmadan kirasını
güncelleyebilmeli; aksi hâlde ilan düzenlenemez hâle geliyor (422 kilidi).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app

EMAIL = "ali@uni.edu.tr"
PASSWORD = "Sifre1234"

# Denetimin tartışmasız engellediği bir metin (bkz. app/moderation.py).
KUFURLU = "Siktir git buradan."


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


def _auth(client) -> dict:
    res = client.post(
        "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
    )
    body = client.post(
        "/api/auth/verify-otp",
        json={"email": EMAIL, "code": res.json()["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _seed_blocked_listing(TestSession, owner_id: int) -> int:
    """Denetime takılan metinli ilanı doğrudan veritabanına yazar.

    API'den geçirilemez (oluşturma 422 verir); amaç zaten kurallar
    sıkılaşmadan ÖNCE yazılmış üretim kaydını taklit etmek.
    """
    with TestSession() as db:
        row = models.Listing(
            owner_id=owner_id,
            type="ev_ilani",
            title="Kadıköy'de 2+1",
            description=KUFURLU,
            district="Kadıköy",
            photos=[],
            rent=18000,
            room_count="2+1",
        )
        db.add(row)
        db.commit()
        return row.id


def test_metin_degismezse_denetim_kosmaz(ctx):
    client, TestSession = ctx
    headers, uid = _auth(client)
    listing_id = _seed_blocked_listing(TestSession, uid)

    # Kira güncellemesi metne dokunmuyor -> geçmeli
    res = client.patch(
        f"/api/listings/{listing_id}", headers=headers, json={"rent": 21000}
    )
    assert res.status_code == 200, res.text
    assert res.json()["rent"] == 21000
    assert res.json()["description"] == KUFURLU

    # Aynı metni bire bir tekrar göndermek de "değişiklik" sayılmaz
    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": KUFURLU, "rent": 22000},
    )
    assert res.status_code == 200, res.text
    assert res.json()["rent"] == 22000


def test_metin_degisirse_denetim_kosar(ctx):
    client, TestSession = ctx
    headers, uid = _auth(client)
    listing_id = _seed_blocked_listing(TestSession, uid)

    # Açıklamayı temiz bir metinle değiştirmek serbest
    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": "Moda'ya 5 dakika, geniş salon."},
    )
    assert res.status_code == 200, res.text

    # Küfürlü yeni metin reddedilir
    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": "Siktir git, ev senin değil."},
    )
    assert res.status_code == 422, res.text

    # Reddedilen güncelleme kaydı bozmadı
    body = client.get(f"/api/listings/{listing_id}").json()
    assert body["description"] == "Moda'ya 5 dakika, geniş salon."


def test_baslik_degisince_denetim_kosar(ctx):
    client, TestSession = ctx
    headers, uid = _auth(client)
    listing_id = _seed_blocked_listing(TestSession, uid)

    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"title": "Siktir git"},
    )
    assert res.status_code == 422, res.text


# ---- kapatılan ilanı düzenleme ve yeniden yayınlama (rakip raporu #5) ----

SCAM = "Evi görmeden kapora gönder, anahtarı kargoyla yollarım."


def _create(client, headers, **over) -> int:
    body = {
        "type": "ev_ilani",
        "title": "Kadıköy'de 2+1",
        "description": "Moda'ya 5 dakika.",
        "district": "Kadıköy",
        "neighborhood": "Caferağa Mah.",
        "photos": [f"https://example.com/{i}.jpg" for i in range(3)],
        "rent": 18000,
        "room_count": "2+1",
        **over,
    }
    res = client.post("/api/listings", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _other(client, email="veli@uni.edu.tr") -> dict:
    res = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": res.json()["dev_code"]}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _mine(client, headers) -> dict[int, dict]:
    return {
        row["id"]: row
        for row in client.get("/api/listings?mine=1", headers=headers).json()
    }


def test_kapatilan_ilan_duzenlenip_yeniden_yayinlanir(ctx):
    client, _ = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers)

    assert client.delete(f"/api/listings/{lid}", headers=headers).status_code == 204
    # "İlanlarım"da kapalı olarak görünür, destede görünmez.
    assert _mine(client, headers)[lid]["is_active"] is False
    assert lid not in [r["id"] for r in client.get("/api/listings").json()]

    # Kapalıyken fiyat güncellenir; ilan kapalı kalır.
    res = client.patch(f"/api/listings/{lid}", headers=headers, json={"rent": 16000})
    assert res.status_code == 200, res.text
    assert (res.json()["rent"], res.json()["is_active"]) == (16000, False)

    res = client.post(f"/api/listings/{lid}/republish", headers=headers)
    assert res.status_code == 200, res.text
    assert (res.json()["is_active"], res.json()["pending_review"]) == (True, False)
    assert lid in [r["id"] for r in client.get("/api/listings").json()]

    # Yayındaki ilanı yeniden yayınlamak anlamsız.
    assert client.post(f"/api/listings/{lid}/republish", headers=headers).status_code == 409


def test_yeniden_yayin_yalnizca_sahibine_acik(ctx):
    client, _ = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers)
    client.delete(f"/api/listings/{lid}", headers=headers)

    assert client.post(f"/api/listings/{lid}/republish").status_code == 401
    assert client.post(
        f"/api/listings/{lid}/republish", headers=_other(client)
    ).status_code == 403
    assert client.post("/api/listings/999/republish", headers=headers).status_code == 404


def test_yeniden_yayinda_metin_yeniden_denetlenir(ctx):
    """Kapalıyken dolandırıcılık kalıbı eklenen ilan yayına değil onaya girer."""
    client, _ = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers)
    client.delete(f"/api/listings/{lid}", headers=headers)

    res = client.patch(f"/api/listings/{lid}", headers=headers, json={"description": SCAM})
    assert res.status_code == 200, res.text
    # Kapalı ilan düzenlemeyle onaya düşmez: sahibi yayına almadı.
    assert (res.json()["is_active"], res.json()["pending_review"]) == (False, False)

    res = client.post(f"/api/listings/{lid}/republish", headers=headers)
    assert res.status_code == 200, res.text
    assert (res.json()["is_active"], res.json()["pending_review"]) == (False, True)
    # Onay beklerken tekrar yayınlamak 409.
    assert client.post(f"/api/listings/{lid}/republish", headers=headers).status_code == 409


def test_engellenen_metinli_kapali_ilan_yeniden_yayinlanamaz(ctx):
    """Kurallar ilan kapalıyken sıkılaşmış olabilir: yayın bugünün kuralıyla."""
    client, TestSession = ctx
    headers, uid = _auth(client)
    lid = _seed_blocked_listing(TestSession, uid)
    with TestSession() as db:
        db.get(models.Listing, lid).is_active = False
        db.commit()

    res = client.post(f"/api/listings/{lid}/republish", headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"]["field"] == "description"
    assert _mine(client, headers)[lid]["is_active"] is False


def test_yoneticinin_kaldirdigi_ilan_sahibine_kapali(ctx):
    client, TestSession = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers)
    with TestSession() as db:
        row = db.get(models.Listing, lid)
        row.is_active = False
        row.moderation_removed = True
        db.commit()

    assert lid not in _mine(client, headers)
    assert client.patch(
        f"/api/listings/{lid}", headers=headers, json={"rent": 1000}
    ).status_code == 404
    assert client.post(f"/api/listings/{lid}/republish", headers=headers).status_code == 404


def test_onay_bekleyen_ilan_duzenlenince_de_kuyrukta_kalir(ctx):
    """Metin temizlense de karar yöneticinin: ilan beklemede ve kuyrukta kalır."""
    client, _ = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers, description=SCAM)

    res = client.patch(
        f"/api/listings/{lid}", headers=headers, json={"description": "Moda'ya 5 dakika."}
    )
    assert res.status_code == 200, res.text
    assert (res.json()["is_active"], res.json()["pending_review"]) == (False, True)

    admin_res = client.post(
        "/api/auth/register", json={"email": "yonetici@uni.edu.tr", "password": PASSWORD}
    )
    token = client.post(
        "/api/auth/verify-otp",
        json={
            "email": "yonetici@uni.edu.tr",
            "code": admin_res.json()["dev_code"],
            "password": PASSWORD,
        },
    ).json()["token"]
    queue = client.get(
        "/api/admin/flagged?kind=listing", headers={"Authorization": f"Bearer {token}"}
    ).json()
    assert [row["id"] for row in queue] == [lid]


def test_ilce_degisince_eski_mahalle_silinir(ctx):
    client, _ = ctx
    headers, _ = _auth(client)
    lid = _create(client, headers)

    res = client.patch(f"/api/listings/{lid}", headers=headers, json={"district": "Beşiktaş"})
    assert res.status_code == 200, res.text
    assert (res.json()["district"], res.json()["neighborhood"]) == ("Beşiktaş", None)

    # Aynı ilçe yeniden gönderilirse mahalle durur.
    client.patch(
        f"/api/listings/{lid}", headers=headers, json={"neighborhood": "Sinanpaşa Mah."}
    )
    res = client.patch(f"/api/listings/{lid}", headers=headers, json={"district": "Beşiktaş"})
    assert res.json()["neighborhood"] == "Sinanpaşa Mah."
