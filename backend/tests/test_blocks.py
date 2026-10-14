"""Engelleme ve eşleşmeyi kaldırma (rakip raporu #7).

Engel iki yönlüdür ve hiçbir satırı silmez: kaldırılınca her şey olduğu
yerden devam eder (bkz. app/blocks.py).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, get_db
from app.main import app


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


def _user(client, email: str, name: str) -> dict:
    res = client.post("/api/auth/register", json={"email": email, "password": "Sifre1234"})
    body = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": res.json()["dev_code"]}
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"id": body["user"]["id"], "headers": headers}


def _listing(client, headers) -> int:
    return client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de oda",
            "description": "Moda'ya yakın.",
            "district": "Kadıköy",
            "photos": [f"https://example.com/{i}.jpg" for i in range(3)],
            "rent": 10000,
            "room_count": "2+1",
        },
    ).json()["id"]


def _deck(client, headers) -> list[int]:
    return [r["id"] for r in client.get("/api/listings?unswiped=1", headers=headers).json()]


def _received(client, headers) -> list[int]:
    return [r["user"]["id"] for r in client.get("/api/swipes/received", headers=headers).json()]


def _matches(client, headers) -> list[int]:
    return [m["id"] for m in client.get("/api/matches", headers=headers).json()]


@pytest.fixture()
def pair(ctx):
    """Ayşe'nin ilanı var, Ali onu yorumla beğendi (henüz eşleşme yok)."""
    client, TestSession = ctx
    ayse = _user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _user(client, "ali@uni.edu.tr", "Ali")
    lid = _listing(client, ayse["headers"])
    res = client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": lid, "direction": "like", "comment": "Merhaba!"},
    )
    assert res.status_code == 200
    return client, TestSession, ayse, ali, lid


def test_engel_begeniyi_ve_desteyi_iki_yonde_gizler(pair):
    client, _, ayse, ali, lid = pair
    ali_lid = _listing(client, ali["headers"])
    assert _received(client, ayse["headers"]) == [ali["id"]]

    assert client.post(
        "/api/blocks", headers=ayse["headers"], json={"user_id": ali["id"]}
    ).status_code == 204

    # Ayşe'nin kuyruğunda Ali yok, eski beğeni kabul edilemez.
    assert _received(client, ayse["headers"]) == []
    swipe_id = client.get("/api/swipes/received", headers=ayse["headers"]).json()
    assert swipe_id == []
    # İki taraf da birbirinin ilanını göremez ve kaydıramaz.
    assert ali_lid not in _deck(client, ayse["headers"])
    assert lid not in _deck(client, ali["headers"])
    assert client.get(f"/api/listings/{lid}", headers=ali["headers"]).status_code == 404
    assert client.post(
        "/api/swipes", headers=ayse["headers"], json={"listing_id": ali_lid, "direction": "like"}
    ).status_code == 404
    # Girişsiz deste etkilenmez.
    assert lid in [r["id"] for r in client.get("/api/listings").json()]


def test_engellenen_begeni_kabul_edilemez(pair):
    client, TestSession, ayse, ali, _ = pair
    swipe_id = client.get("/api/swipes/received", headers=ayse["headers"]).json()[0]["swipe_id"]
    client.post("/api/blocks", headers=ali["headers"], json={"user_id": ayse["id"]})

    res = client.post(
        f"/api/swipes/{swipe_id}/respond", headers=ayse["headers"], json={"accept": True}
    )
    assert res.status_code == 404
    with TestSession() as db:
        assert db.scalar(select(func.count(models.Match.id))) == 0


def test_eslesmeyi_kaldirmak_sohbeti_iki_taraftan_da_kaldirir(pair):
    client, TestSession, ayse, ali, _ = pair
    swipe_id = client.get("/api/swipes/received", headers=ayse["headers"]).json()[0]["swipe_id"]
    match_id = client.post(
        f"/api/swipes/{swipe_id}/respond", headers=ayse["headers"], json={"accept": True}
    ).json()["match_id"]
    assert client.post(
        f"/api/matches/{match_id}/messages", headers=ali["headers"], json={"content": "Selam"}
    ).status_code == 201

    # Ali eşleşmeyi kaldırır (= Ayşe'yi engeller).
    client.post("/api/blocks", headers=ali["headers"], json={"user_id": ayse["id"]})
    for person in (ayse, ali):
        assert _matches(client, person["headers"]) == []
        assert client.get(
            f"/api/matches/{match_id}/messages", headers=person["headers"]
        ).status_code == 404
        assert client.post(
            f"/api/matches/{match_id}/messages",
            headers=person["headers"],
            json={"content": "Orada mısın?"},
        ).status_code == 404

    # Satırlar durur: engeli YALNIZCA koyan kaldırabilir.
    client.delete(f"/api/blocks/{ali['id']}", headers=ayse["headers"])
    assert _matches(client, ayse["headers"]) == []

    assert client.delete(f"/api/blocks/{ayse['id']}", headers=ali["headers"]).status_code == 204
    assert _matches(client, ayse["headers"]) == [match_id]
    texts = [
        m["content"]
        for m in client.get(f"/api/matches/{match_id}/messages", headers=ayse["headers"]).json()
    ]
    assert texts == ["Merhaba!", "Selam"]


def test_engel_listesi_yalnizca_engelleyene_gorunur(pair):
    client, _, ayse, ali, _ = pair
    client.post("/api/blocks", headers=ayse["headers"], json={"user_id": ali["id"]})
    # İkinci kez basmak zararsız.
    client.post("/api/blocks", headers=ayse["headers"], json={"user_id": ali["id"]})

    mine = client.get("/api/blocks", headers=ayse["headers"]).json()
    assert [(b["user_id"], b["name"]) for b in mine] == [(ali["id"], "Ali")]
    # Engellenen kişi, engellendiğini bu listeden öğrenemez.
    assert client.get("/api/blocks", headers=ali["headers"]).json() == []


def test_kendini_ve_olmayan_kullaniciyi_engelleme(ctx):
    client, TestSession = ctx
    ayse = _user(client, "ayse@uni.edu.tr", "Ayşe")
    assert client.post(
        "/api/blocks", headers=ayse["headers"], json={"user_id": ayse["id"]}
    ).status_code == 400
    # Olmayan id: var olanla aynı yanıt, ama satır yazılmaz.
    assert client.post(
        "/api/blocks", headers=ayse["headers"], json={"user_id": 999}
    ).status_code == 204
    with TestSession() as db:
        assert db.scalar(select(func.count(models.Block.id))) == 0
    assert client.post("/api/blocks", json={"user_id": 1}).status_code == 401


def test_engelleyen_ya_da_engellenen_hesabini_silebilir(pair):
    client, TestSession, ayse, ali, _ = pair
    client.post("/api/blocks", headers=ayse["headers"], json={"user_id": ali["id"]})
    assert client.request(
        "DELETE", "/api/auth/me", headers=ali["headers"], json={"password": "Sifre1234"}
    ).status_code == 204
    with TestSession() as db:
        assert db.scalar(select(func.count(models.Block.id))) == 0
