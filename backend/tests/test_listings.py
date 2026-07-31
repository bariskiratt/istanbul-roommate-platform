"""/api/listings CRUD testleri.

Gerçek dosya yerine bellek-içi SQLite kullanılır (get_db override), böylece
testler yerel app.db'ye dokunmaz ve her koşuda temiz başlar.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

EV_ILANI = {
    "type": "ev_ilani",
    "title": "Kadıköy'de güneşli 2+1",
    "description": "Moda'ya 5 dakika, geniş salon.",
    "district": "Kadıköy",
    "photos": ["https://example.com/a.jpg"],
    "rent": 18000,
    "room_count": "2+1",
    "smoking_allowed": False,
    "pets_allowed": True,
}

KISISEL_ILAN = {
    "type": "kisisel_ilan",
    "title": "Beşiktaş'ta ev arkadaşı arıyorum",
    "description": "3. sınıf öğrencisiyim, sakinim.",
    "district": "Beşiktaş",
    "photos": [],
    "budget_min": 8000,
    "budget_max": 14000,
}


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
    # Context manager kullanmıyoruz ki lifespan (ağır veri yükleme) çalışmasın;
    # bu testler yalnızca router'a bakar.
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_and_get_ev_ilani(client):
    res = client.post("/api/listings", json=EV_ILANI)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["id"] == 1
    assert body["rent"] == 18000
    assert body["is_active"] is True

    res = client.get("/api/listings/1")
    assert res.status_code == 200
    assert res.json()["title"] == EV_ILANI["title"]


def test_create_kisisel_ilan(client):
    res = client.post("/api/listings", json=KISISEL_ILAN)
    assert res.status_code == 201, res.text
    assert res.json()["budget_max"] == 14000


def test_list_newest_first_and_filters(client):
    client.post("/api/listings", json=EV_ILANI)
    client.post("/api/listings", json=KISISEL_ILAN)

    res = client.get("/api/listings")
    assert res.status_code == 200
    items = res.json()
    assert [i["id"] for i in items] == [2, 1]  # en yeni önce

    res = client.get("/api/listings", params={"type": "ev_ilani"})
    assert [i["id"] for i in res.json()] == [1]

    res = client.get("/api/listings", params={"district": "Beşiktaş"})
    assert [i["id"] for i in res.json()] == [2]


def test_ev_ilani_requires_rent_and_rooms(client):
    payload = {k: v for k, v in EV_ILANI.items() if k not in ("rent", "room_count")}
    res = client.post("/api/listings", json=payload)
    assert res.status_code == 422


def test_kisisel_ilan_budget_order(client):
    payload = KISISEL_ILAN | {"budget_min": 15000, "budget_max": 8000}
    res = client.post("/api/listings", json=payload)
    assert res.status_code == 422


def test_patch_requires_owner(client):
    # Anonim ilan: sahibi yok -> kimse PATCH edemez
    client.post("/api/listings", json=EV_ILANI)
    res = client.patch("/api/listings/1", json={"rent": 20000})
    assert res.status_code == 403

    # Sahipli ilan: sahibi günceller, yabancı 403 alır
    reg = client.post(
        "/api/auth/register", json={"email": "ali@uni.edu.tr", "password": "Sifre1234"}
    )
    token = client.post(
        "/api/auth/verify-otp",
        json={"email": "ali@uni.edu.tr", "code": reg.json()["dev_code"]},
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/listings", json=EV_ILANI, headers=headers)

    res = client.patch("/api/listings/2", json={"rent": 20000}, headers=headers)
    assert res.status_code == 200
    assert res.json()["rent"] == 20000
    assert client.patch("/api/listings/2", json={"rent": 1}).status_code == 403


def test_deactivate_hides_listing(client):
    client.post("/api/listings", json=EV_ILANI)
    res = client.delete("/api/listings/1")
    assert res.status_code == 204

    assert client.get("/api/listings/1").status_code == 404
    assert client.get("/api/listings").json() == []

    # ikinci silme 404
    assert client.delete("/api/listings/1").status_code == 404
