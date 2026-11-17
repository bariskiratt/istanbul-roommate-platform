"""İlan onayı — app.listing_review ve onu kullanan uçlar.

Kapsam: mod seçimi (varsayılan "all", tanınmayan değer "all"), "all" modunda
yeni ilan / yeniden yayın / metin ve fotoğraf değişikliğinin onaya düşmesi,
yöneticinin onaylaması ve SEBEPLE reddetmesi, sahibinin reddedileni düzeltip
yeniden göndermesi, onay kuyruğunda fotoğrafların görünmesi, "first"
modunun güven kuralı, "flagged" modunun eski davranışı ve yöneticiye giden
bildirim postasının sıklık sınırı ile içeriği.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import emailer, listing_review, models
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]

PHOTOS = [
    "https://example.com/1.jpg",
    "https://example.com/2.jpg",
    "https://example.com/3.jpg",
]
NEW_PHOTOS = [
    "https://example.com/4.jpg",
    "https://example.com/5.jpg",
    "https://example.com/6.jpg",
]
# moderation.HOLD_FOR_REVIEW kalıbı: her modda onaya düşer.
SCAM_TEXT = "Evi görmeden kapora gönderin, IBAN'a hemen yatırın."


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


@pytest.fixture()
def review_all(monkeypatch):
    monkeypatch.setenv("LISTING_REVIEW", "all")


@pytest.fixture()
def review_first(monkeypatch):
    monkeypatch.setenv("LISTING_REVIEW", "first")


def _make_user(client, email, name="Kullanıcı") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    data = client.post(
        "/api/auth/verify-otp",
        json={"email": email, "code": code, "password": "Sifre1234"},
    ).json()
    headers = {"Authorization": f"Bearer {data['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"id": data["user"]["id"], "token": data["token"], "headers": headers}


def _payload(**overrides) -> dict:
    return {
        "type": "ev_ilani",
        "title": "Kadıköy'de güneşli 2+1",
        "description": "Moda'ya 5 dakika, geniş salon.",
        "district": "Kadıköy",
        "photos": PHOTOS,
        "rent": 18000,
        "room_count": "2+1",
    } | overrides


def _create(client, headers, **overrides) -> dict:
    res = client.post("/api/listings", headers=headers, json=_payload(**overrides))
    assert res.status_code == 201, res.text
    return res.json()


def _public_ids(client) -> set[int]:
    return {row["id"] for row in client.get("/api/listings").json()}


def _mine(client, headers, listing_id) -> dict:
    rows = client.get("/api/listings?mine=1", headers=headers).json()
    return next(row for row in rows if row["id"] == listing_id)


def _review(client, admin, listing_id, action, note=None):
    body = {"action": action}
    if note is not None:
        body["note"] = note
    return client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json=body,
    )


# ---------------------------------------------------------------------------
# mod seçimi
# ---------------------------------------------------------------------------


def test_varsayilan_mod_all(monkeypatch):
    monkeypatch.delenv("LISTING_REVIEW", raising=False)
    assert listing_review.mode() == "all"


@pytest.mark.parametrize("raw", ["herkes", "", "  ", "none", "off"])
def test_taninmayan_deger_all_sayilir(monkeypatch, raw):
    """Yanlış yazılmış ayarın cezası fazladan onay olmalı, denetimsiz yayın değil."""
    monkeypatch.setenv("LISTING_REVIEW", raw)
    assert listing_review.mode() == "all"


@pytest.mark.parametrize("raw,expected", [("FIRST", "first"), (" flagged ", "flagged")])
def test_mod_buyuk_kucuk_harf_ve_bosluk_duyarsiz(monkeypatch, raw, expected):
    monkeypatch.setenv("LISTING_REVIEW", raw)
    assert listing_review.mode() == expected


# ---------------------------------------------------------------------------
# "all" modu
# ---------------------------------------------------------------------------


def test_all_yeni_ilan_onaya_duser_ve_destede_gorunmez(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    created = _create(client, ali["headers"])

    assert created["pending_review"] is True
    assert created["is_active"] is False
    assert created["id"] not in _public_ids(client)
    # Sahibi kendi listesinde görür (kayboldu sanmasın).
    assert _mine(client, ali["headers"], created["id"])["pending_review"] is True
    # Tek ilan ucu da yayında olmayanı vermez.
    assert client.get(f"/api/listings/{created['id']}").status_code == 404


def test_all_onay_kuyrugunda_fotograflar_gorunur(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])

    queue = client.get("/api/admin/flagged?kind=listing", headers=admin["headers"])
    assert queue.status_code == 200
    row = next(r for r in queue.json() if r["id"] == created["id"])
    assert row["pending_review"] is True
    assert row["photos"] == PHOTOS
    # Özet kartı da sayar.
    summary = client.get("/api/admin/summary", headers=admin["headers"]).json()
    assert summary["pending_listings"] == 1


def test_all_onaylanan_ilan_yayina_girer(client, ctx, review_all):
    _, Session = ctx
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])

    res = _review(client, admin, created["id"], "clear")
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is True

    assert created["id"] in _public_ids(client)
    with Session() as db:
        row = db.get(models.Listing, created["id"])
        assert row.approved_at is not None
        assert row.pending_review is False
        assert row.rejection_reason is None


def test_all_ret_sebebi_zorunlu(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])

    assert _review(client, admin, created["id"], "reject").status_code == 422
    assert _review(client, admin, created["id"], "reject", "   ").status_code == 422
    # Karar verilmedi: ilan hâlâ bekliyor.
    assert _mine(client, ali["headers"], created["id"])["pending_review"] is True


def test_all_reddedilen_ilan_sebebiyle_sahibine_doner(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])

    reason = "Fotoğraflar evin değil, internetten alınmış görünüyor."
    res = _review(client, admin, created["id"], "reject", reason)
    assert res.status_code == 200, res.text
    assert res.json()["action"] == "reject"
    assert res.json()["is_active"] is False
    # Reddetmek kaldırmak değildir: sahibi ilanı görmeye devam eder.
    assert res.json()["moderation_removed"] is False

    mine = _mine(client, ali["headers"], created["id"])
    assert mine["is_active"] is False
    assert mine["pending_review"] is False
    assert mine["rejection_reason"] == reason
    assert created["id"] not in _public_ids(client)
    # Kuyruktan düşer: karar verildi.
    queue = client.get("/api/admin/flagged?kind=listing", headers=admin["headers"]).json()
    assert created["id"] not in {r["id"] for r in queue}


def test_all_reddedilen_ilan_duzeltilip_yeniden_gonderilir(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "reject", "Fotoğraflar evin değil.")

    # Sahibi fotoğrafları değiştirir: ilan kapalı kalır, sebep düzeltme
    # boyunca görünür.
    edited = client.patch(
        f"/api/listings/{created['id']}",
        headers=ali["headers"],
        json={"photos": NEW_PHOTOS},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["is_active"] is False
    assert edited.json()["rejection_reason"] == "Fotoğraflar evin değil."

    # Yeniden gönderir: yine onaya düşer, eski sebep temizlenir.
    res = client.post(f"/api/listings/{created['id']}/republish", headers=ali["headers"])
    assert res.status_code == 200, res.text
    assert res.json()["pending_review"] is True
    assert res.json()["rejection_reason"] is None

    assert _review(client, admin, created["id"], "clear").status_code == 200
    assert created["id"] in _public_ids(client)


def test_reject_yalniz_onay_bekleyen_ilana(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "clear")

    # Yayındaki ilan reddedilmez; onun için "remove" var.
    res = _review(client, admin, created["id"], "reject", "Sebep")
    assert res.status_code == 400
    assert created["id"] in _public_ids(client)


def test_reject_mesaja_uygulanmaz(client, review_all):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    res = client.post(
        "/api/admin/flagged/message/1/review",
        headers=admin["headers"],
        json={"action": "reject", "note": "Sebep"},
    )
    # Mesaj yoksa 404, varsa 400: ikisi de "uygulanmadı".
    assert res.status_code in (400, 404)


def test_all_yayindaki_ilanin_fotografi_degisince_yeniden_onaya_duser(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "clear")

    res = client.patch(
        f"/api/listings/{created['id']}",
        headers=ali["headers"],
        json={"photos": NEW_PHOTOS},
    )
    assert res.status_code == 200, res.text
    assert res.json()["pending_review"] is True
    assert res.json()["is_active"] is False
    assert created["id"] not in _public_ids(client)

    # Kuyrukta YENİ fotoğraflar görünür.
    queue = client.get("/api/admin/flagged?kind=listing", headers=admin["headers"]).json()
    row = next(r for r in queue if r["id"] == created["id"])
    assert row["photos"] == NEW_PHOTOS


def test_all_yayindaki_ilanin_metni_degisince_yeniden_onaya_duser(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "clear")

    res = client.patch(
        f"/api/listings/{created['id']}",
        headers=ali["headers"],
        json={"description": "Moda'ya 5 dakika, geniş salon, yeni boyandı."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["pending_review"] is True


def test_all_kira_ve_ozellik_degisikligi_onaysiz(client, review_all):
    """İçerik riski taşımayan alanlar ilanı desteden düşürmemeli."""
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "clear")

    res = client.patch(
        f"/api/listings/{created['id']}",
        headers=ali["headers"],
        # Fotoğraflar AYNI liste olarak gönderilse de değişiklik sayılmaz.
        json={"rent": 17000, "furnished": True, "photos": PHOTOS},
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is True
    assert res.json()["pending_review"] is False
    assert created["id"] in _public_ids(client)


def test_all_kapatilip_acilan_ilan_yeniden_onaya_duser(client, review_all):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])
    _review(client, admin, created["id"], "clear")

    assert client.delete(f"/api/listings/{created['id']}", headers=ali["headers"]).status_code == 204
    res = client.post(f"/api/listings/{created['id']}/republish", headers=ali["headers"])
    assert res.status_code == 200, res.text
    assert res.json()["pending_review"] is True
    assert created["id"] not in _public_ids(client)


def test_all_yoneticinin_kendi_ilani_beklemez(client, review_all):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, admin["headers"])
    assert created["is_active"] is True
    assert created["pending_review"] is False


def test_all_yonetici_yayina_alinca_onaylanmis_sayilir(client, ctx, review_all):
    _, Session = ctx
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    created = _create(client, ali["headers"])

    res = client.post(
        f"/api/admin/listings/{created['id']}/publish", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    with Session() as db:
        assert db.get(models.Listing, created["id"]).approved_at is not None


def test_onay_bekleyen_ilan_sahibi_disinda_kimseye_gorunmez(client, review_all):
    """Giriş yapmış başka bir öğrenci de beklemedeki ilanı göremez."""
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    created = _create(client, ali["headers"])

    ids = {r["id"] for r in client.get("/api/listings", headers=ayse["headers"]).json()}
    assert created["id"] not in ids
    deck = client.get("/api/listings?unswiped=1", headers=ayse["headers"]).json()
    assert created["id"] not in {r["id"] for r in deck}
    assert (
        client.get(f"/api/listings/{created['id']}", headers=ayse["headers"]).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# "first" modu
# ---------------------------------------------------------------------------


def test_first_ilk_ilan_onaya_sonrakiler_dogrudan(client, review_first):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")

    first = _create(client, ali["headers"])
    assert first["pending_review"] is True
    # Onaylanmadan açılan ikinci ilan da bekler: güven henüz yok.
    second = _create(client, ali["headers"], title="Üsküdar'da 1+1 oda")
    assert second["pending_review"] is True

    _review(client, admin, first["id"], "clear")
    third = _create(client, ali["headers"], title="Beşiktaş'ta 3+1")
    assert third["is_active"] is True
    assert third["pending_review"] is False

    # Güvenilir kişinin fotoğraf değişikliği de onaysız geçer.
    res = client.patch(
        f"/api/listings/{third['id']}",
        headers=ali["headers"],
        json={"photos": NEW_PHOTOS},
    )
    assert res.json()["is_active"] is True


def test_first_guven_kisiye_ozel(client, review_first):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    first = _create(client, ali["headers"])
    _review(client, admin, first["id"], "clear")

    assert _create(client, ayse["headers"])["pending_review"] is True


def test_first_kaldirilan_ilani_olan_guvenilir_degil(client, review_first):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    first = _create(client, ali["headers"])
    _review(client, admin, first["id"], "clear")
    second = _create(client, ali["headers"], title="Üsküdar'da 1+1 oda")
    assert second["is_active"] is True

    # Yönetici ikinci ilanı kaldırır: güven düşer.
    _review(client, admin, second["id"], "remove", "Kural dışı fotoğraf")
    third = _create(client, ali["headers"], title="Beşiktaş'ta 3+1")
    assert third["pending_review"] is True


def test_first_eski_ilani_olan_kisi_guvenilir_sayilmaz(client, ctx, review_first):
    """approved_at sütunundan önceki ilanları hiçbir yönetici onaylamadı."""
    _, Session = ctx
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    with Session() as db:
        db.add(
            models.Listing(
                owner_id=ali["id"],
                type="ev_ilani",
                title="Eski ilan",
                description="Onay sütunundan önce açılmış.",
                district="Kadıköy",
                photos=PHOTOS,
                rent=15000,
                room_count="2+1",
                is_active=True,
            )
        )
        db.commit()
    assert _create(client, ali["headers"])["pending_review"] is True


# ---------------------------------------------------------------------------
# "flagged" modu ve her modda geçerli kurallar
# ---------------------------------------------------------------------------


def test_flagged_temiz_ilan_hemen_yayinda(client, monkeypatch):
    monkeypatch.setenv("LISTING_REVIEW", "flagged")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    created = _create(client, ali["headers"])
    assert created["is_active"] is True
    assert created["id"] in _public_ids(client)


@pytest.mark.parametrize("mode", ["all", "first", "flagged"])
def test_dolandiricilik_kalibi_her_modda_bekler(client, monkeypatch, mode):
    monkeypatch.setenv("LISTING_REVIEW", mode)
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    if mode == "first":
        # Güvenilir kişi bile dolandırıcılık kalıbında bekler.
        trusted = _create(client, ali["headers"])
        _review(client, admin, trusted["id"], "clear")
    created = _create(client, ali["headers"], description=SCAM_TEXT)
    assert created["pending_review"] is True


# ---------------------------------------------------------------------------
# yöneticiye bildirim postası
# ---------------------------------------------------------------------------


@pytest.fixture()
def sent(monkeypatch):
    """E-postayı açık gösterir ve gönderilenleri yakalar (ağa çıkmaz)."""
    calls: list[tuple[list[str], int]] = []
    # Yalnızca listing_review'un gördüğü e-posta modülü değişir: kayıt
    # kodları (auth) gerçek emailer'dan DEV_OTP yoluyla gitmeye devam eder.
    stub = SimpleNamespace(
        email_enabled=lambda: True,
        send_review_notice=lambda to, count: calls.append((list(to), count)) or True,
    )
    monkeypatch.setattr(listing_review, "emailer", stub)
    return calls


def test_bekleyen_ilan_yoneticilere_bildirilir(client, review_all, sent):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _create(client, ali["headers"])
    assert sent == [(sorted(ADMIN_EMAILS), 1)]


def test_bildirim_yarim_saatte_bir(client, review_all, sent):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _create(client, ali["headers"])
    _create(client, ali["headers"], title="Üsküdar'da 1+1 oda")
    assert len(sent) == 1


def test_yayina_dogrudan_giren_ilan_bildirilmez(client, monkeypatch, sent):
    monkeypatch.setenv("LISTING_REVIEW", "flagged")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _create(client, ali["headers"])
    assert sent == []


def test_bildirim_postasi_kullanici_metni_tasimaz(monkeypatch):
    """Postada yalnız sayı ve panel adresi var; başlık/isim sızmaz."""
    captured: list[dict] = []
    monkeypatch.setenv("BREVO_API_KEY", "test")
    monkeypatch.setenv("EMAIL_FROM", "noreply@evdes.tr")
    monkeypatch.setattr(emailer, "_send", lambda payload: captured.append(payload) or True)

    assert emailer.send_review_notice(["yonetici@uni.edu.tr"], 3) is True
    payload = captured[0]
    assert payload["subject"] == "Onay bekleyen 3 ilan var"
    assert payload["to"] == [{"email": "yonetici@uni.edu.tr"}]
    assert "https://evdes.tr/admin" in payload["textContent"]
    assert "https://evdes.tr/admin" in payload["htmlContent"]


def test_bildirim_postasi_eposta_kapaliyken_gitmez(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    assert emailer.send_review_notice(["yonetici@uni.edu.tr"], 1) is False
