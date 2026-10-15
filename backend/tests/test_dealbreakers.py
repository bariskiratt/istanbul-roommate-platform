"""İstemediklerim (app.dealbreakers): kesin eleme, iki yönlü."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app

PHOTOS = [
    "https://example.com/1.jpg",
    "https://example.com/2.jpg",
    "https://example.com/3.jpg",
]


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


def _user(client, email: str, **profile) -> dict:
    """Kayıt + doğrulama + profil; istek başlıklarını döner."""
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    res = client.patch(
        "/api/auth/me", headers=headers, json={"name": email.split("@")[0], **profile}
    )
    assert res.status_code == 200, res.text
    return headers


def _listing(client, headers, title: str, **fields) -> int:
    body = {
        "type": "ev_ilani",
        "title": title,
        "description": "test",
        "district": "Kadıköy",
        "photos": PHOTOS,
        "rent": 10000,
        "room_count": "2+1",
        **fields,
    }
    res = client.post("/api/listings", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _personal(client, headers, title: str) -> int:
    return _listing(
        client,
        headers,
        title,
        type="kisisel_ilan",
        rent=None,
        room_count=None,
        budget_min=5000,
        budget_max=9000,
    )


def _deck_titles(client, headers) -> set[str]:
    res = client.get("/api/listings?unswiped=1", headers=headers)
    assert res.status_code == 200
    return {row["title"] for row in res.json()}


# ---- profil alanı ----


def test_yeni_kullanicida_bos_liste_doner(client):
    h = _user(client, "a@uni.edu.tr")
    assert client.get("/api/auth/me", headers=h).json()["dealbreakers"] == []


def test_secim_kaydedilir_tekrar_atilir_null_temizler(client):
    h = _user(client, "a@uni.edu.tr")
    res = client.patch(
        "/api/auth/me",
        headers=h,
        json={"dealbreakers": ["smoking", "night_owl", "smoking"]},
    )
    assert res.status_code == 200
    assert res.json()["dealbreakers"] == ["smoking", "night_owl"]

    res = client.patch("/api/auth/me", headers=h, json={"dealbreakers": None})
    assert res.json()["dealbreakers"] == []


def test_bilinmeyen_anahtar_reddedilir(client):
    h = _user(client, "a@uni.edu.tr")
    res = client.patch(
        "/api/auth/me", headers=h, json={"dealbreakers": ["gender"]}
    )
    assert res.status_code == 422


def test_secim_baskasina_gitmez(client):
    """Kişinin elediği özellikler ilanında ya da Beğeniler'de görünmez."""
    owner = _user(client, "owner@uni.edu.tr", dealbreakers=["alcohol"])
    lid = _listing(client, owner, "Ev ilanı")
    viewer = _user(client, "viewer@uni.edu.tr")

    row = client.get(f"/api/listings/{lid}", headers=viewer).json()
    assert "dealbreakers" not in row
    assert "dealbreakers" not in (row["owner_profile"] or {})

    my = _listing(client, viewer, "Benim ilanım")
    client.post("/api/swipes", headers=owner, json={"listing_id": my, "direction": "like"})
    liker = client.get("/api/swipes/received", headers=viewer).json()[0]["user"]
    assert "dealbreakers" not in liker


# ---- deste ----


def test_secimi_olmayan_icin_deste_degismez(client):
    smoker = _user(client, "s@uni.edu.tr", smoking=True, sleep_schedule="gece")
    _listing(client, smoker, "Sigara içilen ev", smoking_allowed=True)
    viewer = _user(client, "v@uni.edu.tr")
    assert _deck_titles(client, viewer) == {"Sigara içilen ev"}


def test_sigara_icen_sahip_ve_sigara_icilen_ev_elenir(client):
    smoker = _user(client, "s@uni.edu.tr", smoking=True)
    _listing(client, smoker, "Sahibi içiyor")
    _personal(client, smoker, "Oda arıyorum, içiyorum")

    host = _user(client, "h@uni.edu.tr", smoking=False)
    _listing(client, host, "Sahibi içmiyor, evde serbest", smoking_allowed=True)
    _listing(client, host, "Sigarasız ev", smoking_allowed=False)

    unknown = _user(client, "u@uni.edu.tr")  # sigara sorusu cevapsız
    _listing(client, unknown, "Cevap yok")

    viewer = _user(client, "v@uni.edu.tr", dealbreakers=["smoking"])
    # Bilinmeyen eleme sebebi değil; yalnızca açıkça "evet" diyen gider.
    assert _deck_titles(client, viewer) == {"Sigarasız ev", "Cevap yok"}


def test_evcil_hayvan_ev_kurali_da_sayilir(client):
    host = _user(client, "h@uni.edu.tr", pets=False)
    _listing(client, host, "Hayvan kabul", pets_allowed=True)
    _listing(client, host, "Hayvansız", pets_allowed=False)
    owner = _user(client, "o@uni.edu.tr", pets=True)
    _personal(client, owner, "Kedimle oda arıyorum")

    viewer = _user(client, "v@uni.edu.tr", dealbreakers=["pets"])
    assert _deck_titles(client, viewer) == {"Hayvansız"}


def test_alkol_ve_uyku_duzeni(client):
    drinker = _user(client, "d@uni.edu.tr", alcohol=True, sleep_schedule="esnek")
    _listing(client, drinker, "Alkol")
    owl = _user(client, "o@uni.edu.tr", alcohol=False, sleep_schedule="gece")
    _listing(client, owl, "Gece")
    lark = _user(client, "l@uni.edu.tr", alcohol=False, sleep_schedule="erken")
    _listing(client, lark, "Erken")

    v1 = _user(client, "v1@uni.edu.tr", dealbreakers=["alcohol"])
    assert _deck_titles(client, v1) == {"Gece", "Erken"}
    v2 = _user(client, "v2@uni.edu.tr", dealbreakers=["night_owl"])
    assert _deck_titles(client, v2) == {"Alkol", "Erken"}
    v3 = _user(client, "v3@uni.edu.tr", dealbreakers=["early_bird", "alcohol"])
    assert _deck_titles(client, v3) == {"Gece"}


def test_beni_eleyenin_ilani_bana_da_gelmez(client):
    """İki yönlü: sigara istemeyen kişinin ilanı sigara içene gösterilmez,
    yoksa beğenisi hiç görülmeyecek bir kuyruğa düşerdi."""
    picky = _user(client, "p@uni.edu.tr", smoking=False, dealbreakers=["smoking"])
    _listing(client, picky, "Sigarasız ev", smoking_allowed=False)

    smoker = _user(client, "s@uni.edu.tr", smoking=True)
    assert _deck_titles(client, smoker) == set()

    non_smoker = _user(client, "n@uni.edu.tr", smoking=False)
    assert _deck_titles(client, non_smoker) == {"Sigarasız ev"}


def test_profil_degisince_deste_hemen_degisir(client):
    smoker = _user(client, "s@uni.edu.tr", smoking=True)
    _listing(client, smoker, "Ev ilanı")
    viewer = _user(client, "v@uni.edu.tr", dealbreakers=["smoking"])
    assert _deck_titles(client, viewer) == set()

    client.patch("/api/auth/me", headers=viewer, json={"dealbreakers": []})
    assert _deck_titles(client, viewer) == {"Ev ilanı"}


def test_girissiz_liste_ve_kendi_ilanlarim_etkilenmez(client):
    me = _user(client, "m@uni.edu.tr", smoking=True, dealbreakers=["smoking"])
    _listing(client, me, "Kendi ilanım", smoking_allowed=True)

    mine = client.get("/api/listings?mine=1", headers=me).json()
    assert [row["title"] for row in mine] == ["Kendi ilanım"]
    anon = client.get("/api/listings").json()
    assert [row["title"] for row in anon] == ["Kendi ilanım"]


def test_genel_liste_de_ayni_kurali_uygular(client):
    """Deste dışındaki ilan listesi (ana sayfa) de aynı kişiyi göstermez."""
    smoker = _user(client, "s@uni.edu.tr", smoking=True)
    _listing(client, smoker, "Ev ilanı")
    viewer = _user(client, "v@uni.edu.tr", dealbreakers=["smoking"])
    assert client.get("/api/listings", headers=viewer).json() == []


# ---- Beğeniler kuyruğu ----


def test_elenen_kisinin_begenisi_kuyrukta_gizlenir_secim_kalkinca_doner(client):
    owner = _user(client, "o@uni.edu.tr", dealbreakers=["smoking"])
    lid = _listing(client, owner, "Ev ilanı", smoking_allowed=False)

    # Beğeni, sahip seçimini yapmadan önce gelmiş gibi: sigara içen kişi
    # ilanı beğenir, sonra sahip seçimini kaydeder.
    client.patch("/api/auth/me", headers=owner, json={"dealbreakers": []})
    smoker = _user(client, "s@uni.edu.tr", smoking=True)
    client.post("/api/swipes", headers=smoker, json={"listing_id": lid, "direction": "like"})
    other = _user(client, "x@uni.edu.tr", smoking=False)
    client.post("/api/swipes", headers=other, json={"listing_id": lid, "direction": "like"})
    assert len(client.get("/api/swipes/received", headers=owner).json()) == 2

    client.patch("/api/auth/me", headers=owner, json={"dealbreakers": ["smoking"]})
    likes = client.get("/api/swipes/received", headers=owner).json()
    assert [row["user"]["name"] for row in likes] == ["x"]

    client.patch("/api/auth/me", headers=owner, json={"dealbreakers": []})
    assert len(client.get("/api/swipes/received", headers=owner).json()) == 2
