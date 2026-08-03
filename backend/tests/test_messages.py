"""Eşleşme içi mesajlaşma testleri."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import moderation
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


def _make_user(client, email, name):
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    body = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"id": body["user"]["id"], "headers": headers}


def _matched_pair(client):
    """Ali + Ayşe'yi eşleştirir, (ali, ayse, match_id) döner."""
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing = client.post(
        "/api/listings",
        headers=ali["headers"],
        json={
            "type": "ev_ilani",
            "title": "Ali'nin evi",
            "description": "t",
            "district": "Kadıköy",
            "photos": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"],
            "rent": 10000,
            "room_count": "2+1",
        },
    ).json()["id"]
    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing, "direction": "like"},
    )
    swipe_id = client.get(
        "/api/swipes/received", headers=ali["headers"]
    ).json()[0]["swipe_id"]
    match_id = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    ).json()["match_id"]
    return ali, ayse, match_id


def test_send_and_list_messages(client):
    ali, ayse, match_id = _matched_pair(client)

    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Selam! Ev hâlâ müsait."},
    )
    assert res.status_code == 201, res.text
    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Harika, ne zaman bakabilirim?"},
    )

    msgs = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert [m["sender_id"] for m in msgs] == [ali["id"], ayse["id"]]
    assert msgs[0]["content"].startswith("Selam")


def test_outsider_cannot_read_or_send(client):
    _, _, match_id = _matched_pair(client)
    deniz = _make_user(client, "deniz@uni.edu.tr", "Deniz")

    # 404 (403 DEĞİL): taraf olmayan için var olan eşleşme ile olmayan
    # eşleşme ayırt edilemez olmalı — bkz. app/messages.py _require_participant.
    assert client.get(
        f"/api/matches/{match_id}/messages", headers=deniz["headers"]
    ).status_code == 404
    assert client.post(
        f"/api/matches/{match_id}/messages",
        headers=deniz["headers"],
        json={"content": "merhaba"},
    ).status_code == 404


def test_unknown_match_404(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    assert client.get(
        "/api/matches/999/messages", headers=ali["headers"]
    ).status_code == 404


def test_empty_message_rejected(client):
    ali, _, match_id = _matched_pair(client)
    assert client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": ""},
    ).status_code == 422


def test_pagination_limit_and_after_id(client):
    ali, ayse, match_id = _matched_pair(client)
    for i in range(5):
        client.post(
            f"/api/matches/{match_id}/messages",
            headers=ali["headers"],
            json={"content": f"mesaj {i}"},
        )

    # limit: son 2 mesaj, kronolojik sırada
    msgs = client.get(
        f"/api/matches/{match_id}/messages",
        params={"limit": 2},
        headers=ayse["headers"],
    ).json()
    assert [m["content"] for m in msgs] == ["mesaj 3", "mesaj 4"]

    # after_id: yalnız yeni mesajlar
    msgs = client.get(
        f"/api/matches/{match_id}/messages",
        params={"after_id": msgs[0]["id"]},
        headers=ayse["headers"],
    ).json()
    assert [m["content"] for m in msgs] == ["mesaj 4"]


def test_matches_include_last_message(client):
    ali, ayse, match_id = _matched_pair(client)
    matches = client.get("/api/matches", headers=ali["headers"]).json()
    assert matches[0]["last_message"] is None

    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "İlk mesaj"},
    )
    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Son mesaj"},
    )
    matches = client.get("/api/matches", headers=ayse["headers"]).json()
    assert matches[0]["last_message"] == "Son mesaj"
    assert matches[0]["last_message_at"] is not None


# ---------------------------------------------------------------------------
# kullanıcı, sistemin ağzından konuşamaz
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("marker", moderation.SYSTEM_MARKERS)
def test_sistem_sabitini_taklit_eden_mesaj_reddedilir(client, marker):
    """"[removed_by_moderation]" / "[unreadable]" kullanıcı metni olamaz.

    Bu dizeler sunucunun ürettiği, DİLDEN BAĞIMSIZ işaretlerdir; arayüz
    onları tanıyıp kendi dilinde bir SİSTEM CÜMLESİ basar. Kullanıcı aynı
    dizeyi yazabildiğinde arayüzü kandırıp "Bu mesaj moderasyon tarafından
    kaldırıldı." cümlesini bastırabiliyordu. Yan etkisi de vardı: yönetici
    panelinde "Mesajı kaldır" düğmesi metin sabite eşitse gizlendiği için
    sahte sabiti yazan kullanıcının mesajı rapor kuyruğundan kaldırılamıyordu.
    """
    ali, ayse, match_id = _matched_pair(client)
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": marker},
    )
    assert res.status_code == 422, res.text
    # Ret metni sabitin kendisini içermez; yoksa doğru yazımı öğretirdik.
    assert marker not in res.json()["detail"]
    assert client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json() == []


@pytest.mark.parametrize("marker", moderation.SYSTEM_MARKERS)
def test_bosluk_ve_buyuk_harfle_kacis_da_reddedilir(client, marker):
    """Kırpma ve büyük/küçük harf farkı korumayı atlatmamalı."""
    ali, ayse, match_id = _matched_pair(client)
    for variant in (f"  {marker} ", marker.upper()):
        res = client.post(
            f"/api/matches/{match_id}/messages",
            headers=ali["headers"],
            json={"content": variant},
        )
        assert res.status_code == 422, (variant, res.text)


def test_sabit_cumle_icinde_gecerse_engellenmez(client):
    """Yanlış pozitif olmasın: arayüz TAM EŞİTLİK arıyor, cümleyi değil."""
    ali, ayse, match_id = _matched_pair(client)
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Mesajın bende [unreadable] görünüyor, tekrar yazar mısın?"},
    )
    assert res.status_code == 201, res.text
