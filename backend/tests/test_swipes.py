"""Swipe ve eşleşme akışı testleri."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


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


def _make_user(client, email: str, name: str) -> dict:
    """Kayıt + doğrulama + isim; {'token', 'id', 'headers'} döner."""
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    body = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"token": body["token"], "id": body["user"]["id"], "headers": headers}


def _make_listing(client, headers, title="İlan") -> int:
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": title,
            "description": "test",
            "district": "Kadıköy",
            "photos": [],
            "rent": 10000,
            "room_count": "2+1",
        },
    )
    return res.json()["id"]


def test_swipe_requires_auth(client):
    assert client.post(
        "/api/swipes", json={"listing_id": 1, "direction": "like"}
    ).status_code == 401


def test_cannot_swipe_own_listing(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ali["headers"])
    res = client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": listing, "direction": "like"},
    )
    assert res.status_code == 400


def test_single_like_no_match_then_mutual_matches(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"], "Ali'nin evi")
    ayse_listing = _make_listing(client, ayse["headers"], "Ayşe'nin evi")

    # Tek taraflı beğeni eşleşme üretmez
    res = client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": ayse_listing, "direction": "like"},
    )
    assert res.json() == {"matched": False, "match_id": None}

    # Karşı beğeni otomatik eşleşme üretir
    res = client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": ali_listing, "direction": "like"},
    )
    body = res.json()
    assert body["matched"] is True

    # İki taraf da eşleşmeyi görür
    for u, other in ((ali, "Ayşe"), (ayse, "Ali")):
        matches = client.get("/api/matches", headers=u["headers"]).json()
        assert len(matches) == 1
        assert matches[0]["other_user"]["name"] == other


def test_pass_does_not_match(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"])
    ayse_listing = _make_listing(client, ayse["headers"])

    client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": ayse_listing, "direction": "like"},
    )
    res = client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": ali_listing, "direction": "pass"},
    )
    assert res.json()["matched"] is False
    assert client.get("/api/matches", headers=ali["headers"]).json() == []


def test_received_likes_and_respond(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"], "Ali'nin evi")

    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": ali_listing, "direction": "like"},
    )

    # Ali beğeniyi kuyruğunda görür
    received = client.get("/api/swipes/received", headers=ali["headers"]).json()
    assert len(received) == 1
    assert received[0]["user"]["name"] == "Ayşe"
    assert received[0]["listing_title"] == "Ali'nin evi"
    swipe_id = received[0]["swipe_id"]

    # Ayşe başkasının beğeni kuyruğunu göremez / cevaplayamaz
    res = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    )
    assert res.status_code == 403

    # Ali kabul eder -> eşleşme
    res = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    )
    assert res.json()["matched"] is True

    # Kuyruk boşaldı, eşleşme listede
    assert client.get("/api/swipes/received", headers=ali["headers"]).json() == []
    matches = client.get("/api/matches", headers=ayse["headers"]).json()
    assert matches[0]["other_user"]["name"] == "Ali"


def test_reject_clears_queue_without_match(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"])

    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": ali_listing, "direction": "like"},
    )
    swipe_id = client.get("/api/swipes/received", headers=ali["headers"]).json()[0]["swipe_id"]
    res = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": False},
    )
    assert res.json()["matched"] is False
    assert client.get("/api/swipes/received", headers=ali["headers"]).json() == []
    assert client.get("/api/matches", headers=ali["headers"]).json() == []


def test_duplicate_match_prevented(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"])
    ayse_listing = _make_listing(client, ayse["headers"])

    client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": ayse_listing, "direction": "like"},
    )
    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": ali_listing, "direction": "like"},
    )
    # Beğeniler kuyruğundan da kabul edilirse ikinci eşleşme doğmamalı
    received = client.get("/api/swipes/received", headers=ayse["headers"]).json()
    if received:
        client.post(
            f"/api/swipes/{received[0]['swipe_id']}/respond",
            headers=ayse["headers"],
            json={"accept": True},
        )
    assert len(client.get("/api/matches", headers=ali["headers"]).json()) == 1