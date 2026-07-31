"""/api/listings CRUD testleri.

Gerçek dosya yerine bellek-içi SQLite kullanılır (get_db override), böylece
testler yerel app.db'ye dokunmaz ve her koşuda temiz başlar.
İlan oluşturma/silme auth ister; testler kayıtlı bir kullanıcıyla koşar.
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


def _auth_headers(client, email="ali@uni.edu.tr") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_requires_auth(client):
    assert client.post("/api/listings", json=EV_ILANI).status_code == 401


def test_create_and_get_ev_ilani(client):
    headers = _auth_headers(client)
    res = client.post("/api/listings", json=EV_ILANI, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["id"] == 1
    assert body["rent"] == 18000
    assert body["is_active"] is True
    assert body["owner_id"] is not None

    res = client.get("/api/listings/1")
    assert res.status_code == 200
    assert res.json()["title"] == EV_ILANI["title"]


def test_create_kisisel_ilan(client):
    headers = _auth_headers(client)
    res = client.post("/api/listings", json=KISISEL_ILAN, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["budget_max"] == 14000


def test_list_newest_first_and_filters(client):
    headers = _auth_headers(client)
    client.post("/api/listings", json=EV_ILANI, headers=headers)
    client.post("/api/listings", json=KISISEL_ILAN, headers=headers)

    res = client.get("/api/listings")
    assert res.status_code == 200
    items = res.json()
    assert [i["id"] for i in items] == [2, 1]  # en yeni önce

    res = client.get("/api/listings", params={"type": "ev_ilani"})
    assert [i["id"] for i in res.json()] == [1]

    res = client.get("/api/listings", params={"district": "Beşiktaş"})
    assert [i["id"] for i in res.json()] == [2]


def test_ev_ilani_requires_rent_and_rooms(client):
    headers = _auth_headers(client)
    payload = {k: v for k, v in EV_ILANI.items() if k not in ("rent", "room_count")}
    res = client.post("/api/listings", json=payload, headers=headers)
    assert res.status_code == 422


def test_kisisel_ilan_budget_order(client):
    headers = _auth_headers(client)
    payload = KISISEL_ILAN | {"budget_min": 15000, "budget_max": 8000}
    res = client.post("/api/listings", json=payload, headers=headers)
    assert res.status_code == 422


def test_patch_owner_only_and_null_safe(client):
    owner = _auth_headers(client, "ali@uni.edu.tr")
    stranger = _auth_headers(client, "veli@uni.edu.tr")
    client.post("/api/listings", json=EV_ILANI, headers=owner)

    # Sahibi günceller
    res = client.patch("/api/listings/1", json={"rent": 20000}, headers=owner)
    assert res.status_code == 200
    assert res.json()["rent"] == 20000

    # Yabancı ve token'sız istek reddedilir
    assert client.patch(
        "/api/listings/1", json={"rent": 1}, headers=stranger
    ).status_code == 403
    assert client.patch("/api/listings/1", json={"rent": 1}).status_code == 403

    # null gönderilen zorunlu alan yok sayılır — kayıt bozulmaz (500 regresyonu)
    res = client.patch("/api/listings/1", json={"rent": None}, headers=owner)
    assert res.status_code == 200
    assert res.json()["rent"] == 20000
    assert client.get("/api/listings").status_code == 200

    # Kısmi bütçe güncellemesi tutarlılığı bozamaz
    client.post("/api/listings", json=KISISEL_ILAN, headers=owner)
    res = client.patch("/api/listings/2", json={"budget_min": 99999}, headers=owner)
    assert res.status_code == 422


def test_deactivate_owner_only(client):
    owner = _auth_headers(client, "ali@uni.edu.tr")
    stranger = _auth_headers(client, "veli@uni.edu.tr")
    client.post("/api/listings", json=EV_ILANI, headers=owner)

    assert client.delete("/api/listings/1").status_code == 401
    assert client.delete("/api/listings/1", headers=stranger).status_code == 403

    assert client.delete("/api/listings/1", headers=owner).status_code == 204
    assert client.get("/api/listings/1").status_code == 404
    assert client.get("/api/listings").json() == []

    # ikinci silme 404
    assert client.delete("/api/listings/1", headers=owner).status_code == 404
