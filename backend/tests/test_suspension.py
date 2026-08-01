"""Kullanıcı askıya alma — giriş kapısı, oturumlar, ilan görünürlüğü.

Askı GERİ ALINABİLİR bir karardır: hiçbir kayıt silinmez, is_active'e
dokunulmaz. Bu dosya asıl olarak "askı kalkınca her şey geri geliyor mu"
sorusunu kovalar.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]
SECOND_ADMIN = sorted(ADMIN_EMAILS)[1] if len(ADMIN_EMAILS) > 1 else None


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
def client(ctx):
    return ctx[0]


def _make_user(client, email, name="Kullanıcı") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    data = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()
    headers = {"Authorization": f"Bearer {data['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"id": data["user"]["id"], "token": data["token"], "headers": headers}


def _make_listing(client, headers, **overrides) -> int:
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de güneşli 2+1",
            "description": "Moda'ya 5 dakika, geniş salon.",
            "district": "Kadıköy",
            "photos": ["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg"],
            "rent": 18000,
            "room_count": "2+1",
        }
        | overrides,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_sebepsiz_askiya_alinabilir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    res = client.post(
        f"/api/admin/users/{ali['id']}/suspend", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["suspended_reason"] is None


def _suspend(client, admin, user_id, reason="Tekrarlayan spam"):
    res = client.post(
        f"/api/admin/users/{user_id}/suspend",
        headers=admin["headers"],
        json={"reason": reason},
    )
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# askıya alma kaydı
# ---------------------------------------------------------------------------

def test_askiya_alma_kim_ne_zaman_neden_kaydeder(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    body = _suspend(client, admin, ali["id"], reason="Sahte ilan")
    assert body["is_suspended"] is True
    assert body["suspended_by"] == admin["id"]
    assert body["suspended_at"] is not None
    assert body["suspended_reason"] == "Sahte ilan"

    listed = client.get(
        "/api/admin/users?suspended=true", headers=admin["headers"]
    ).json()
    assert [u["id"] for u in listed] == [ali["id"]]

    body = client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    ).json()
    assert body["is_suspended"] is False
    assert body["suspended_by"] is None
    assert body["suspended_at"] is None
    assert body["suspended_reason"] is None
    assert client.get(
        "/api/admin/users?suspended=true", headers=admin["headers"]
    ).json() == []


def test_yonetici_kendini_askiya_alamaz(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    res = client.post(
        f"/api/admin/users/{admin['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "deneme"},
    )
    assert res.status_code == 400, res.text


@pytest.mark.skipif(
    SECOND_ADMIN is None, reason="Kurulumda tek yönetici e-postası tanımlı"
)
def test_yonetici_baska_yoneticiyi_askiya_alamaz(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    other = _make_user(client, SECOND_ADMIN, "Diğer Yönetici")
    res = client.post(
        f"/api/admin/users/{other['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "deneme"},
    )
    assert res.status_code == 403, res.text


def test_olmayan_kullanici_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    # Gövde tümüyle atlanabilir (sebepsiz askı) — 422 değil 404 beklenir.
    assert client.post(
        "/api/admin/users/9999/suspend", headers=admin["headers"]
    ).status_code == 404
    assert client.post(
        "/api/admin/users/9999/unsuspend", headers=admin["headers"]
    ).status_code == 404


# ---------------------------------------------------------------------------
# giriş kapısı
# ---------------------------------------------------------------------------

def test_askidaki_kullanici_sifreyle_giremez(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _suspend(client, admin, ali["id"], reason="Sahte ilan")

    res = client.post(
        "/api/auth/login",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    )
    assert res.status_code == 403, res.text
    assert "askıya" in res.json()["detail"]
    assert "Sahte ilan" in res.json()["detail"]

    # Askı kalkınca aynı şifreyle girebilir.
    client.post(f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"])
    res = client.post(
        "/api/auth/login",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    )
    assert res.status_code == 200, res.text


def test_askidaki_kullanici_otp_yoluyla_da_giremez(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    # Askıdan ÖNCE kod al: geçerli kod elde olsa bile askı delinmemeli.
    code = client.post(
        "/api/auth/request-otp", json={"email": "ali@uni.edu.tr"}
    ).json()["dev_code"]
    _suspend(client, admin, ali["id"])

    assert client.post(
        "/api/auth/request-otp", json={"email": "ali@uni.edu.tr"}
    ).status_code == 403
    res = client.post(
        "/api/auth/verify-otp", json={"email": "ali@uni.edu.tr", "code": code}
    )
    assert res.status_code == 403, res.text

    client.post(f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"])
    res = client.post(
        "/api/auth/verify-otp", json={"email": "ali@uni.edu.tr", "code": code}
    )
    assert res.status_code == 200, res.text


def test_askiya_alinca_mevcut_jetonlar_silinir(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    assert client.get("/api/auth/me", headers=ali["headers"]).status_code == 200

    _suspend(client, admin, ali["id"])

    assert client.get("/api/auth/me", headers=ali["headers"]).status_code == 401
    with Session() as db:
        assert db.query(models.AuthToken).filter_by(user_id=ali["id"]).count() == 0

    # Askı kalksa bile ESKİ jeton geri gelmez; kullanıcı yeniden giriş yapar.
    client.post(f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"])
    assert client.get("/api/auth/me", headers=ali["headers"]).status_code == 401
    token = client.post(
        "/api/auth/login",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    ).json()["token"]
    assert client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 200


# ---------------------------------------------------------------------------
# ilan görünürlüğü
# ---------------------------------------------------------------------------

def test_askidaki_kullanicinin_ilanlari_gizlenir_ve_geri_gelir(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    ali_listing = _make_listing(client, ali["headers"])
    ayse_listing = _make_listing(client, ayse["headers"], district="Beşiktaş")

    assert {i["id"] for i in client.get("/api/listings").json()} == {
        ali_listing,
        ayse_listing,
    }

    _suspend(client, admin, ali["id"])

    assert [i["id"] for i in client.get("/api/listings").json()] == [ayse_listing]
    assert client.get(f"/api/listings/{ali_listing}").status_code == 404
    assert client.get(f"/api/listings/{ali_listing}/fair-price").status_code == 404
    # Deste ve filtreli listeler de elemeli. (unswiped kişinin KENDİ ilanını
    # zaten çıkarır; burada bakılan Ali'nin ilanının desteye hiç girmemesi.)
    assert client.get(
        "/api/listings", headers=ayse["headers"], params={"unswiped": True}
    ).json() == []
    assert client.get("/api/listings", params={"district": "Kadıköy"}).json() == []

    # is_active'e DOKUNULMADI: satır yayında sayılmaya devam ediyor.
    with Session() as db:
        assert db.get(models.Listing, ali_listing).is_active is True

    client.post(f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"])
    assert {i["id"] for i in client.get("/api/listings").json()} == {
        ali_listing,
        ayse_listing,
    }


def test_askidaki_sahibin_ilani_kaydirilamaz(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ali["headers"])

    _suspend(client, admin, ali["id"])
    res = client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing_id, "direction": "like"},
    )
    assert res.status_code == 404, res.text

    client.post(f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"])
    res = client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing_id, "direction": "like"},
    )
    assert res.status_code == 200, res.text


def test_askidaki_kullanici_begeni_ve_eslesme_listelerinden_dusar(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ali["headers"])
    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing_id, "direction": "like"},
    )
    assert len(client.get("/api/swipes/received", headers=ali["headers"]).json()) == 1

    _suspend(client, admin, ayse["id"])
    assert client.get("/api/swipes/received", headers=ali["headers"]).json() == []

    client.post(f"/api/admin/users/{ayse['id']}/unsuspend", headers=admin["headers"])
    received = client.get("/api/swipes/received", headers=ali["headers"]).json()
    assert len(received) == 1

    # Eşleşme kurulduktan sonra askı gelirse sohbet listeden düşer, silinmez.
    match_id = client.post(
        f"/api/swipes/{received[0]['swipe_id']}/respond",
        headers=ali["headers"],
        json={"accept": True},
    ).json()["match_id"]
    assert [m["id"] for m in client.get(
        "/api/matches", headers=ali["headers"]
    ).json()] == [match_id]

    _suspend(client, admin, ayse["id"])
    assert client.get("/api/matches", headers=ali["headers"]).json() == []

    client.post(f"/api/admin/users/{ayse['id']}/unsuspend", headers=admin["headers"])
    assert [m["id"] for m in client.get(
        "/api/matches", headers=ali["headers"]
    ).json()] == [match_id]


# ---------------------------------------------------------------------------
# mesajlaşma
# ---------------------------------------------------------------------------

def _match_pair(client, ali, ayse):
    """Ali ile Ayşe'yi eşleştirir; match_id döner."""
    listing_id = _make_listing(client, ali["headers"])
    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing_id, "direction": "like"},
    )
    swipe_id = client.get(
        "/api/swipes/received", headers=ali["headers"]
    ).json()[0]["swipe_id"]
    return client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    ).json()["match_id"]


def test_askidaki_kullaniciya_mesaj_gonderilemez_gecmis_okunur(client):
    """Askı tutarlı olmalı: sohbet listede yokken mesaj kabul edilmemeli.

    GEÇMİŞ KAYBOLMAZ — okuma ucuna dokunulmuyor, yalnız yeni mesaj engelleniyor.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    match_id = _match_pair(client, ali, ayse)

    assert client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Merhaba, ev hâlâ boş mu?"},
    ).status_code == 201

    _suspend(client, admin, ayse["id"])

    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Cevap alamadım."},
    )
    assert res.status_code == 403, res.text
    assert "askıya" in res.json()["detail"]

    # Sohbet geçmişi yerinde ve okunabilir.
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert [r["content"] for r in rows] == ["Merhaba, ev hâlâ boş mu?"]

    # Askı kalkınca mesajlaşma aynen geri gelir.
    client.post(f"/api/admin/users/{ayse['id']}/unsuspend", headers=admin["headers"])
    assert client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Cevap alamadım."},
    ).status_code == 201


def test_askidakinin_begenisi_respond_ucundan_islenemez(ctx):
    """Askı, /api/swipes/received filtresiyle bitmiyor: respond da korunmalı.

    Eski bir swipe_id elde bırakılmışsa (kullanıcı ekranı yenilemeden askı
    gelirse ya da id doğrudan gönderilirse) respond ucu askıdaki kullanıcıyla
    eşleşme yaratıyordu. Sonuç ÖLÜ EŞLEŞME: istemci "Eşleştiniz!" yanıtı
    alıyor, ama eşleşme /api/matches'ten elendiği için hiçbir listede
    görünmüyor ve mesaj da gönderilemiyordu.

    404 seçildi (403 değil): ilan sahibinin yetkisi var, ORTADA İŞLENECEK
    GEÇERLİ BİR BEĞENİ YOK. /api/swipes/received zaten bu beğeniyi
    listelemiyor; uç kendi listesiyle tutarlı konuşuyor ve karşı tarafın
    askıda olduğunu sızdırmıyor.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ali["headers"])
    client.post(
        "/api/swipes",
        headers=ayse["headers"],
        json={"listing_id": listing_id, "direction": "like"},
    )
    swipe_id = client.get(
        "/api/swipes/received", headers=ali["headers"]
    ).json()[0]["swipe_id"]

    _suspend(client, admin, ayse["id"])

    res = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    )
    assert res.status_code == 404, res.text
    # Ne eşleşme doğdu ne de "eşleştiniz" denildi.
    with Session() as db:
        assert db.query(models.Match).count() == 0

    # RET de engellenir: askı geri alınabilir bir karardır, responded=True
    # yazsaydık askı kalkınca geri gelmesi gereken beğeni geri gelmezdi.
    assert client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": False},
    ).status_code == 404

    client.post(f"/api/admin/users/{ayse['id']}/unsuspend", headers=admin["headers"])
    assert [
        r["swipe_id"]
        for r in client.get("/api/swipes/received", headers=ali["headers"]).json()
    ] == [swipe_id]
    assert client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    ).json()["matched"] is True


# ---------------------------------------------------------------------------
# askı gerekçesinin sızması
# ---------------------------------------------------------------------------

# Yöneticinin askı notu SERBEST METİNDİR: şüphenin ayrıntısını, hangi ihbara
# dayandığını, IP/kimlik bilgisi taşıyabilir. Aşağıdaki testler bu notun
# YALNIZCA kimliğini kanıtlayan hesap sahibine gösterildiğini kovalar.
#
# Bulunan hata: /request-otp ve /verify-otp askı kontrolünü kimlik
# doğrulamadan ÖNCE çalıştırıyor ve yanıta notu ekliyordu. Sonuç: yalnızca
# e-posta adresini bilen bir yabancı, şifre ya da kod olmadan notun tamamını
# okuyabiliyordu.

GIZLI_GEREKCE = "Dolandırıcılık şüphesi — kimlik doğrulanamadı, IP Romanya"


def test_request_otp_aski_gerekcesini_sizdirmaz(client):
    """Kimlik bilgisi İSTEMEYEN uç yöneticinin notunu vermemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _suspend(client, admin, ali["id"], reason=GIZLI_GEREKCE)

    # Saldırgan yalnızca e-postayı biliyor: şifre YOK, kod YOK.
    res = client.post("/api/auth/request-otp", json={"email": "ali@uni.edu.tr"})

    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert GIZLI_GEREKCE not in detail, detail
    assert "Sebep" not in detail, detail
    assert detail == "Hesabın yönetici tarafından askıya alındı."


def test_verify_otp_aski_gerekcesini_sizdirmaz(client):
    """Kod doğrulanmadan da bu uca gelinebiliyor; not verilmemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _suspend(client, admin, ali["id"], reason=GIZLI_GEREKCE)

    # Rastgele, kesinlikle yanlış bir kod.
    res = client.post(
        "/api/auth/verify-otp", json={"email": "ali@uni.edu.tr", "code": "000000"}
    )

    assert res.status_code == 403, res.text
    detail = res.json()["detail"]
    assert GIZLI_GEREKCE not in detail, detail
    assert "Sebep" not in detail, detail


def test_login_gerekceyi_SIFRE_DOGRULANDIKTAN_sonra_gosterir(client):
    """Hesabın sahibi neyi düzelteceğini öğrenebilmeli.

    Gerekçenin gösterildiği TEK yer burasıdır ve kontrol şifre
    doğrulandıktan SONRA koşar; yani karşıdaki gerçekten hesabın sahibidir.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _suspend(client, admin, ali["id"], reason=GIZLI_GEREKCE)

    # DOĞRU şifreyle: gerekçe görünür.
    res = client.post(
        "/api/auth/login",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    )
    assert res.status_code == 403, res.text
    assert GIZLI_GEREKCE in res.json()["detail"]

    # YANLIŞ şifreyle: askıdan da gerekçeden de haber yok, sıradan 401.
    res = client.post(
        "/api/auth/login",
        json={"email": "ali@uni.edu.tr", "password": "TamamenBaska9"},
    )
    assert res.status_code == 401, res.text
    detail = res.json()["detail"]
    assert GIZLI_GEREKCE not in detail, detail
    assert "askıya" not in detail, detail
