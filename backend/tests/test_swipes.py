"""Swipe ve eşleşme akışı testleri."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

# config.ADMIN_EMAILS ortamdan okunur; kurulum farkı testi kırmasın diye
# listeden birini alıyoruz.
ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]


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


# ---- DELETE /api/swipes/mine (deste sıfırlama, yalnız yönetici) ----

def test_deste_sifirlama_yalniz_admin(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    assert client.delete("/api/swipes/mine", headers=ali["headers"]).status_code == 403
    # Giriş yapmadan da erişilemez
    assert client.delete("/api/swipes/mine").status_code == 401


def test_admin_destesini_sifirlar(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    l1 = _make_listing(client, ayse["headers"], "Ev 1")
    l2 = _make_listing(client, ayse["headers"], "Ev 2")

    for lid, yon in ((l1, "like"), (l2, "pass")):
        client.post(
            "/api/swipes",
            headers=admin["headers"],
            json={"listing_id": lid, "direction": yon},
        )
    # Kararlar verildi: deste boşaldı
    assert client.get(
        "/api/listings", headers=admin["headers"], params={"unswiped": True}
    ).json() == []

    res = client.delete("/api/swipes/mine", headers=admin["headers"])
    assert res.status_code == 200, res.text
    assert res.json() == {"deleted": 2}

    # Deste geri geldi
    ids = [
        i["id"]
        for i in client.get(
            "/api/listings", headers=admin["headers"], params={"unswiped": True}
        ).json()
    ]
    assert sorted(ids) == [l1, l2]

    # İkinci sıfırlama silecek kayıt bulamaz
    assert client.delete(
        "/api/swipes/mine", headers=admin["headers"]
    ).json() == {"deleted": 0}


def test_deste_sifirlama_eslesmeyi_ve_sohbeti_korur(client):
    """Kaydırmalar silinse de eşleşme ve mesaj geçmişi yerinde kalmalı."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    admin_listing = _make_listing(client, admin["headers"], "Yöneticinin evi")
    ayse_listing = _make_listing(client, ayse["headers"], "Ayşe'nin evi")

    client.post(
        "/api/swipes",
        headers=admin["headers"],
        json={"listing_id": ayse_listing, "direction": "like"},
    )
    match_id = client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": admin_listing, "direction": "like"},
    ).json()["match_id"]
    client.post(
        f"/api/matches/{match_id}/messages",
        headers=admin["headers"],
        json={"content": "Merhaba, ev müsait mi?"},
    )

    assert client.delete(
        "/api/swipes/mine", headers=admin["headers"]
    ).json() == {"deleted": 1}

    # Eşleşme ve mesaj duruyor
    matches = client.get("/api/matches", headers=admin["headers"]).json()
    assert [m["id"] for m in matches] == [match_id]
    msgs = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert [m["content"] for m in msgs] == ["Merhaba, ev müsait mi?"]

    # Tekrar beğeni ikinci bir eşleşme doğurmaz
    res = client.post(
        "/api/swipes",
        headers=admin["headers"],
        json={"listing_id": ayse_listing, "direction": "like"},
    )
    assert res.json() == {"matched": True, "match_id": match_id}
    assert len(client.get("/api/matches", headers=admin["headers"]).json()) == 1