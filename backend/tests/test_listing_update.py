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
