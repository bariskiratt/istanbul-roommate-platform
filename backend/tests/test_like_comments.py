"""Hinge tarzı beğeni: fotoğrafa / karta beğeni, yorum ve eşleşmede sohbete taşınması.

Kurallar (app/swipes.py):
- Beğeni ilanın tamamına, bir fotoğrafına ya da bir kartına verilebilir.
- Fotoğrafta dizin gönderilir, sunucu ADRESİ ilandan okuyup saklar.
- Yorum mesaj gibi denetlenir ve şifreli saklanır.
- Eşleşme olunca yorum sohbetin ilk mesajı olur, bir kez.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import content_limits, crypto, models
from app.db import Base, get_db
from app.main import app

PHOTOS = [
    "https://example.com/1.jpg",
    "https://example.com/2.jpg",
    "https://example.com/3.jpg",
]


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


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setenv(crypto.KEY_ENV, crypto.generate_key())
    crypto.reset_cache()
    yield
    crypto.reset_cache()


def _make_user(client, email: str, name: str, **profile) -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    body = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name, **profile})
    return {"id": body["user"]["id"], "headers": headers}


def _make_listing(client, headers, title="İlan") -> int:
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": title,
            "description": "Kadıköy'de güneşli oda",
            "district": "Kadıköy",
            "photos": PHOTOS,
            "rent": 10000,
            "room_count": "2+1",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _like(client, user, listing_id, **extra):
    return client.post(
        "/api/swipes",
        headers=user["headers"],
        json={"listing_id": listing_id, "direction": "like", **extra},
    )


def _received(client, user):
    return client.get("/api/swipes/received", headers=user["headers"]).json()


def _messages(client, user, match_id):
    return client.get(
        f"/api/matches/{match_id}/messages", headers=user["headers"]
    ).json()


# ---- hedef ----

def test_fotograf_begenisi_adresi_ilandan_okur(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(client, ali, listing, target={"kind": "photo", "photo_index": 2})
    assert res.status_code == 200, res.text

    [like] = _received(client, ayse)
    assert like["target"] == {
        "kind": "photo",
        "photo_url": PHOTOS[2],
        "prompt_key": None,
    }
    assert like["comment"] is None


def test_ilanda_olmayan_fotograf_reddedilir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(client, ali, listing, target={"kind": "photo", "photo_index": 3})
    assert res.status_code == 422
    # Reddedilen beğeni kaydedilmez; deste kartı yeniden gösterebilsin.
    assert _received(client, ayse) == []


def test_adres_gonderilemez_yalnizca_dizin(ctx):
    """İstemcinin yazdığı adres saklanmaz: hedef şemasında adres alanı yok."""
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(
        client,
        ali,
        listing,
        target={"kind": "photo", "photo_url": "https://evil.example/x.jpg"},
    )
    assert res.status_code == 422


def test_kart_begenisi_anahtari_dondurur(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(client, ali, listing, target={"kind": "prompt", "prompt_key": "sleep"})
    assert res.status_code == 200, res.text
    [like] = _received(client, ayse)
    assert like["target"]["kind"] == "prompt"
    assert like["target"]["prompt_key"] == "sleep"


def test_bilinmeyen_kart_anahtari_reddedilir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(client, ali, listing, target={"kind": "prompt", "prompt_key": "maas"})
    assert res.status_code == 422


def test_gecte_hedef_ve_yorum_reddedilir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = client.post(
        "/api/swipes",
        headers=ali["headers"],
        json={"listing_id": listing, "direction": "pass", "comment": "Selam"},
    )
    assert res.status_code == 422


def test_eski_bicim_hedefsiz_begeni_calisir(ctx):
    """Hedef ve yorum isteğe bağlı: eski istemci aynen çalışmaya devam eder."""
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    assert _like(client, ali, listing).status_code == 200
    [like] = _received(client, ayse)
    assert like["target"] is None
    assert like["comment"] is None


# ---- yorum ----

def test_yorum_alana_gorunur_ve_sifreli_saklanir(ctx, key):
    client, Session = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(
        client,
        ali,
        listing,
        target={"kind": "photo", "photo_index": 0},
        comment="  Bu balkon harika, oda hâlâ boş mu?  ",
    )
    assert res.status_code == 200, res.text

    [like] = _received(client, ayse)
    assert like["comment"] == "Bu balkon harika, oda hâlâ boş mu?"

    with Session() as db:
        row = db.scalars(select(models.Swipe)).one()
    assert row.comment.startswith(crypto.PREFIX)
    assert "balkon" not in row.comment


def test_bos_yorum_yorumsuz_sayilir(ctx):
    client, Session = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    assert _like(client, ali, listing, comment="   ").status_code == 200
    with Session() as db:
        assert db.scalars(select(models.Swipe)).one().comment is None


def test_uzun_yorum_reddedilir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    assert _like(client, ali, listing, comment="a" * 301).status_code == 422


def test_kufurlu_yorum_reddedilir_begeni_kaydedilmez(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    res = _like(client, ali, listing, comment="siktir git buradan")
    assert res.status_code == 422
    assert res.json()["detail"].startswith("Yorumda")
    # Kullanıcının yazdığı kelime hata metnine yansımaz.
    assert "siktir" not in res.json()["detail"]
    assert _received(client, ayse) == []


def test_sistem_sabiti_yorum_olamaz(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    assert _like(client, ali, listing, comment=crypto.UNREADABLE).status_code == 422


def test_isaretli_yorum_iletilir_isaret_mesaja_gecer(ctx):
    """"flag" yorumu durdurmaz; eşleşince işaret mesajla yönetici kuyruğuna düşer."""
    client, Session = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    assert _like(client, ali, listing, comment="Bence bu fiyat aptalca.").status_code == 200
    [like] = _received(client, ayse)
    assert like["comment"] == "Bence bu fiyat aptalca."

    res = client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    )
    match_id = res.json()["match_id"]
    with Session() as db:
        msg = db.scalars(
            select(models.Message).where(models.Message.match_id == match_id)
        ).one()
    assert msg.is_flagged is True
    assert msg.flag_reasons


def test_yorum_hiz_siniri(ctx, monkeypatch):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listings = [_make_listing(client, ayse["headers"], f"İlan {i}") for i in range(3)]

    window = content_limits.LIMITS["like_comment"][1]
    monkeypatch.setitem(content_limits.LIMITS, "like_comment", (2, window))
    assert _like(client, ali, listings[0], comment="Merhaba").status_code == 200
    assert _like(client, ali, listings[1], comment="Merhaba").status_code == 200
    assert _like(client, ali, listings[2], comment="Merhaba").status_code == 429
    # Yorumsuz beğeni sınıra girmez.
    assert _like(client, ali, listings[2]).status_code == 200


# ---- eşleşme ve sohbet ----

def test_kabul_edilince_yorum_sohbetin_ilk_mesaji_olur(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    _like(
        client,
        ali,
        listing,
        target={"kind": "prompt", "prompt_key": "sleep"},
        comment="Ben de gece kuşuyum!",
    )
    [like] = _received(client, ayse)
    res = client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    ).json()
    assert res["matched"] is True

    msgs = _messages(client, ayse, res["match_id"])
    assert [(m["sender_id"], m["content"]) for m in msgs] == [
        (ali["id"], "Ben de gece kuşuyum!")
    ]
    # Sohbet listesinin önizlemesi de yorumu gösterir.
    [match] = client.get("/api/matches", headers=ayse["headers"]).json()
    assert match["last_message"] == "Ben de gece kuşuyum!"


def test_reddedilen_yorum_sohbete_tasinmaz(ctx):
    """"Geç" denen yorum, ikisi sonra başka bir ilandan eşleşse bile gelmez."""
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse_listing = _make_listing(client, ayse["headers"])
    ali_listing = _make_listing(client, ali["headers"], "Ali'nin ilanı")

    _like(client, ali, ayse_listing, comment="İlk yorum")
    [like] = _received(client, ayse)
    client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": False},
    )

    # Ayşe sonra Ali'nin ilanını beğenir; Ali'nin eski beğenisi karşılıklı
    # beğeni sayılır ve eşleşme doğar.
    res = _like(client, ayse, ali_listing).json()
    assert res["matched"] is True
    assert _messages(client, ali, res["match_id"]) == []


def test_karsilikli_begenide_iki_yorum_sirayla_gelir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse_listing = _make_listing(client, ayse["headers"])
    ali_listing = _make_listing(client, ali["headers"], "Ali'nin ilanı")

    assert _like(client, ali, ayse_listing, comment="Önce ben yazdım").json()["matched"] is False
    res = _like(
        client,
        ayse,
        ali_listing,
        target={"kind": "photo", "photo_index": 1},
        comment="Sonra ben",
    ).json()
    assert res["matched"] is True

    msgs = _messages(client, ali, res["match_id"])
    assert [(m["sender_id"], m["content"]) for m in msgs] == [
        (ali["id"], "Önce ben yazdım"),
        (ayse["id"], "Sonra ben"),
    ]


def test_yorum_bir_kez_tasinir(ctx):
    """Karşılıklı beğeniyle eşleştikten sonra Beğeniler'de kabul, yorumu ikinci kez yazmaz."""
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse_listing = _make_listing(client, ayse["headers"])
    ali_listing = _make_listing(client, ali["headers"], "Ali'nin ilanı")

    _like(client, ali, ayse_listing, comment="Merhaba")
    match_id = _like(client, ayse, ali_listing).json()["match_id"]
    assert len(_messages(client, ayse, match_id)) == 1

    # Ali'nin beğenisi Ayşe'nin kuyruğunda hâlâ duruyor; kabul etmek aynı
    # eşleşmeyi bulur ve yorumu tekrarlamaz.
    [like] = _received(client, ayse)
    client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    )
    assert len(_messages(client, ayse, match_id)) == 1


def test_eslesmeden_sonra_gelen_yeni_yorum_kabulde_eklenir(ctx):
    client, _ = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    first = _make_listing(client, ayse["headers"], "Birinci")
    second = _make_listing(client, ayse["headers"], "İkinci")

    _like(client, ali, first, comment="Birinci yorum")
    [like] = _received(client, ayse)
    match_id = client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    ).json()["match_id"]

    _like(client, ali, second, comment="İkinci yorum")
    [like] = _received(client, ayse)
    again = client.post(
        f"/api/swipes/{like['swipe_id']}/respond",
        headers=ayse["headers"],
        json={"accept": True},
    ).json()
    assert again["match_id"] == match_id
    assert [m["content"] for m in _messages(client, ayse, match_id)] == [
        "Birinci yorum",
        "İkinci yorum",
    ]


def test_hesap_silinince_yorumlu_begeni_de_gider(ctx):
    client, Session = ctx
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])
    _like(client, ali, listing, comment="Merhaba")

    res = client.request(
        "DELETE",
        "/api/auth/me",
        headers=ali["headers"],
        json={"password": "Sifre1234"},
    )
    assert res.status_code == 204, res.text
    assert _received(client, ayse) == []
    with Session() as db:
        assert db.scalars(select(models.Swipe)).all() == []


# ---- ilan sahibinin profil özeti ----

def test_ilan_sahibinin_profil_ozeti_yalnizca_girisliye_gider(ctx):
    client, _ = ctx
    ayse = _make_user(
        client,
        "ayse@uni.edu.tr",
        "Ayşe",
        sleep_schedule="gece",
        smoking=False,
        pets=True,
        department="Mimarlık",
        year=3,
        budget_min=8000,
        budget_max=12000,
        bio="Gizli kalmalı",
    )
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing = _make_listing(client, ayse["headers"])

    anon = client.get(f"/api/listings/{listing}").json()
    assert anon["owner_profile"] is None
    assert all(row["owner_profile"] is None for row in client.get("/api/listings").json())

    profile = client.get(f"/api/listings/{listing}", headers=ali["headers"]).json()[
        "owner_profile"
    ]
    assert profile == {
        "department": "Mimarlık",
        "year": 3,
        "sleep_schedule": "gece",
        "smoking": False,
        "pets": True,
        "alcohol": None,
        "photo": None,
    }
    # Bütçe, semtler ve bio ilan kartında yer almaz.
    assert "budget_min" not in profile and "bio" not in profile
