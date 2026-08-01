"""Yönetici moderasyon uçları — /api/admin/*.

Kapsam: yetki matrisi (401/403/200), bildirim kuyruğu ve çözme, işaretlenen
içerik kuyruğu, "clear"/"remove" incelemesi, KALDIRILANI GERİ ALMA (restore),
kaldırılan içeriğin bulunabilirliği (?status=removed) ve özet kartları.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crypto, models, moderation
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

# config.ADMIN_EMAILS ortam değişkeninden okunur; testte listeden birini alıp
# yönetici hesabını onunla kuruyoruz ki kurulum farkı testi kırmasın.
ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]

# Denetimin "flag" verdiği, ENGELLEMEDİĞİ metinler (bkz. test_moderation.py).
FLAGGED_LISTING_TEXT = "Detaylar için ara: 0532 123 45 67"
FLAGGED_MESSAGE_TEXT = "Bence bu fiyat aptalca."


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


def _listing_payload(**overrides) -> dict:
    return {
        "type": "ev_ilani",
        "title": "Kadıköy'de güneşli 2+1",
        "description": "Moda'ya 5 dakika, geniş salon.",
        "district": "Kadıköy",
        "photos": [],
        "rent": 18000,
        "room_count": "2+1",
    } | overrides


def _make_listing(client, headers, **overrides) -> int:
    res = client.post(
        "/api/listings", headers=headers, json=_listing_payload(**overrides)
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _matched_pair(client):
    """Ali + Ayşe'yi eşleştirir; (ali, ayse, match_id) döner."""
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
    match_id = client.post(
        f"/api/swipes/{swipe_id}/respond",
        headers=ali["headers"],
        json={"accept": True},
    ).json()["match_id"]
    return ali, ayse, match_id


def _report(client, headers, target_type, target_id, reason="spam", note=None):
    res = client.post(
        "/api/reports",
        headers=headers,
        json={
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "note": note,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------------------------------------------------------------------------
# yetki matrisi
# ---------------------------------------------------------------------------

# (method, path, gövde) — her yönetici ucu tek tek denenir. Yeni bir uç
# eklenince buraya da yazılmalı: yetkisiz erişim en pahalı hatadır.
ADMIN_ENDPOINTS = [
    ("get", "/api/admin/summary", None),
    ("get", "/api/admin/reports", None),
    ("get", "/api/admin/reports?status=all", None),
    ("patch", "/api/admin/reports/1", {"resolved": True}),
    ("get", "/api/admin/flagged", None),
    ("get", "/api/admin/flagged?kind=listing", None),
    ("get", "/api/admin/flagged?status=removed", None),
    ("post", "/api/admin/flagged/listing/1/review", {"action": "clear"}),
    ("post", "/api/admin/listing/1/restore", None),
    ("post", "/api/admin/message/1/restore", None),
    ("get", "/api/admin/users", None),
    ("get", "/api/admin/users?suspended=true", None),
    ("post", "/api/admin/users/1/suspend", {"reason": "spam"}),
    ("post", "/api/admin/users/1/unsuspend", None),
]


def _call(client, method, path, body=None, headers=None):
    # TestClient.get() "json" argümanı kabul etmez; gövde yalnızca varsa geçilir.
    kwargs = {}
    if body is not None:
        kwargs["json"] = body
    if headers is not None:
        kwargs["headers"] = headers
    return getattr(client, method)(path, **kwargs)


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
def test_girissiz_erisim_401(client, method, path, body):
    assert _call(client, method, path, body).status_code == 401


@pytest.mark.parametrize("method,path,body", ADMIN_ENDPOINTS)
def test_admin_olmayan_403(client, method, path, body):
    user = _make_user(client, "ali@uni.edu.tr", "Ali")
    res = _call(client, method, path, body, headers=user["headers"])
    assert res.status_code == 403, res.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/admin/summary",
        "/api/admin/reports",
        "/api/admin/reports?status=all",
        "/api/admin/reports?status=resolved",
        "/api/admin/flagged",
        "/api/admin/flagged?kind=listing",
        "/api/admin/flagged?kind=message",
        "/api/admin/flagged?status=removed",
        "/api/admin/flagged?kind=message&status=removed",
        # NOT: "/api/admin/users" filtresiz ARTIK 422 — bkz.
        # test_kullanici_listesi_suspended_filtresi_zorunlu.
        "/api/admin/users?suspended=true",
        "/api/admin/users?suspended=false",
    ],
)
def test_admin_get_uclari_200(client, path):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    res = client.get(path, headers=admin["headers"])
    assert res.status_code == 200, res.text


def test_admin_yazma_uclari_200(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    report_id = _report(client, ali["headers"], "listing", listing_id)

    assert client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": True},
    ).status_code == 200
    assert client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "clear"},
    ).status_code == 200
    assert client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Spam ilan"},
    ).status_code == 200
    assert client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    ).status_code == 200


# ---------------------------------------------------------------------------
# özet
# ---------------------------------------------------------------------------

def test_ozet_sayilari(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    temiz = _make_listing(client, ali["headers"])
    _make_listing(client, ali["headers"], description=FLAGGED_LISTING_TEXT)
    _report(client, ali["headers"], "listing", temiz)

    body = client.get("/api/admin/summary", headers=admin["headers"]).json()
    assert body == {
        "open_reports": 1,
        "flagged_listings": 1,
        "flagged_messages": 0,
        "suspended_users": 0,
        "total_users": 2,
        "active_listings": 2,
    }


# ---------------------------------------------------------------------------
# bildirim kuyruğu
# ---------------------------------------------------------------------------

def test_rapor_satiri_karar_baglami_tasir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ayse["headers"])
    report_id = _report(
        client, ali["headers"], "listing", listing_id, note="Sahte ilan"
    )

    rows = client.get("/api/admin/reports", headers=admin["headers"]).json()
    assert [r["id"] for r in rows] == [report_id]
    row = rows[0]
    assert row["reporter_id"] == ali["id"]
    assert row["reporter_name"] == "Ali"
    assert row["note"] == "Sahte ilan"
    assert row["target"] == {
        "kind": "listing",
        "id": listing_id,
        "deleted": False,
        "title": "Kadıköy'de güneşli 2+1",
        "district": "Kadıköy",
        "is_active": True,
        "is_flagged": False,
        "owner_id": ayse["id"],
        "owner_name": "Ayşe",
    }


def test_kullanici_ve_mesaj_hedefleri_ozetlenir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Merhaba, ev hâlâ boş mu?"},
    ).json()["id"]

    _report(client, ali["headers"], "user", ayse["id"], reason="taciz")
    _report(client, ali["headers"], "message", msg_id, reason="taciz")

    rows = client.get("/api/admin/reports", headers=admin["headers"]).json()
    by_type = {r["target_type"]: r["target"] for r in rows}

    assert by_type["user"]["name"] == "Ayşe"
    assert by_type["user"]["is_suspended"] is False
    # Raporlanan mesajın METNİ döner (çözülmüş); sohbetin tamamı DÖNMEZ.
    assert by_type["message"]["content"] == "Merhaba, ev hâlâ boş mu?"
    assert by_type["message"]["sender_id"] == ayse["id"]
    assert by_type["message"]["sender_name"] == "Ayşe"


def test_hedefi_silinmis_rapor_uc_patlatmaz(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ayse["headers"])
    _report(client, ali["headers"], "listing", listing_id)

    # İlan veritabanından tamamen silinirse (elle temizlik, eski veri) rapor
    # satırı yetim kalır — kuyruk yine de açılabilmeli.
    with Session() as db:
        db.delete(db.get(models.Listing, listing_id))
        db.commit()

    res = client.get("/api/admin/reports", headers=admin["headers"])
    assert res.status_code == 200, res.text
    assert res.json()[0]["target"] == {
        "kind": "listing",
        "id": listing_id,
        "deleted": True,
    }


def test_rapor_cozulunce_kim_ne_zaman_yazilir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ayse["headers"])
    report_id = _report(client, ali["headers"], "listing", listing_id)

    res = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": True, "resolution_note": "İlan yayından kaldırıldı."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["resolved"] is True
    assert body["resolved_by"] == admin["id"]
    assert body["resolved_at"] is not None
    assert body["resolution_note"] == "İlan yayından kaldırıldı."

    # Çözülmüş rapor açık kuyrukta görünmez, resolved kuyruğunda görünür.
    assert client.get("/api/admin/reports", headers=admin["headers"]).json() == []
    resolved = client.get(
        "/api/admin/reports?status=resolved", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in resolved] == [report_id]
    assert len(
        client.get("/api/admin/reports?status=all", headers=admin["headers"]).json()
    ) == 1


def test_rapor_yeniden_acilinca_cozen_izi_silinir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ayse["headers"])
    report_id = _report(client, ali["headers"], "listing", listing_id)

    client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": True},
    )
    body = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": False},
    ).json()
    assert body["resolved"] is False
    assert body["resolved_by"] is None
    assert body["resolved_at"] is None
    assert len(client.get("/api/admin/reports", headers=admin["headers"]).json()) == 1


def test_rapor_yeniden_acilinca_karar_notu_da_silinir(client):
    """Yukarıdaki test NOTSUZ kapatmayı dener; asıl tehlike NOTLU olanda.

    İstemci raporu yeniden açarken not alanını hiç göndermiyor. Not sunucuda
    kalırsa bildirim, GERİ ALINMIŞ bir kararın notuyla kuyruğa döner ve
    yönetici ekranında o not basılır.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ayse["headers"])
    report_id = _report(client, ali["headers"], "listing", listing_id)

    closed = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": True, "resolution_note": "Asılsız ihbar."},
    ).json()
    assert closed["resolution_note"] == "Asılsız ihbar."

    # İstemcinin gerçekten gönderdiği gövde: yalnızca resolved.
    body = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=admin["headers"],
        json={"resolved": False},
    ).json()
    assert body["resolved"] is False
    assert body["resolution_note"] is None

    queued = client.get("/api/admin/reports", headers=admin["headers"]).json()
    assert [r["id"] for r in queued] == [report_id]
    assert queued[0]["resolution_note"] is None


def test_olmayan_rapor_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    res = client.patch(
        "/api/admin/reports/9999", headers=admin["headers"], json={"resolved": True}
    )
    assert res.status_code == 404, res.text


# ---------------------------------------------------------------------------
# işaretlenen içerik kuyruğu
# ---------------------------------------------------------------------------

def test_isaretlenen_ilan_gerekcesiyle_listelenir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _make_listing(client, ali["headers"])  # temiz ilan kuyruğa girmez
    flagged_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )

    rows = client.get(
        "/api/admin/flagged?kind=listing", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in rows] == [flagged_id]
    row = rows[0]
    assert row["kind"] == "listing"
    assert row["content"] == FLAGGED_LISTING_TEXT
    assert row["author_id"] == ali["id"]
    assert row["author_name"] == "Ali"
    assert row["is_active"] is True
    # Gerekçeler moderation.ModerationResult.reasons biçiminde saklanır.
    assert f"{moderation.ILETISIM}:telefon" in row["flag_reasons"]
    assert row["flag_reasons_text"]


def test_isaretlenen_mesaj_metniyle_listelenir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]

    rows = client.get(
        "/api/admin/flagged?kind=message", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in rows] == [msg_id]
    row = rows[0]
    assert row["content"] == FLAGGED_MESSAGE_TEXT
    assert row["author_id"] == ayse["id"]
    assert row["match_id"] == match_id
    assert any(r.startswith(moderation.HAKARET) for r in row["flag_reasons"])


def test_flagged_all_iki_turu_birlestirir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _, ayse, match_id = _matched_pair(client)
    _make_listing(client, ayse["headers"], description=FLAGGED_LISTING_TEXT)
    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    )
    rows = client.get("/api/admin/flagged", headers=admin["headers"]).json()
    assert {r["kind"] for r in rows} == {"listing", "message"}


def test_ilan_clear_isareti_kaldirir_yayini_surdurur(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )

    res = client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "clear", "note": "İçerik temiz."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["is_flagged"] is False
    assert body["is_active"] is True
    assert body["content_removed"] is False
    assert body["reviewed_by"] == admin["id"]
    assert body["reviewed_at"] is not None
    assert body["review_note"] == "İçerik temiz."

    # Kuyruktan düşer, ilan yayında kalır.
    assert client.get("/api/admin/flagged", headers=admin["headers"]).json() == []
    assert [i["id"] for i in client.get("/api/listings").json()] == [listing_id]
    with Session() as db:
        assert db.get(models.Listing, listing_id).is_active is True


def test_ilan_remove_yayindan_kaldirir_satiri_silmez(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )

    body = client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "remove", "note": "Sahte ilan."},
    ).json()
    assert body["is_active"] is False
    assert body["is_flagged"] is False
    # Sahibin kendi kapattığı ilandan ayıran bayrak: geri almayı bu sağlar.
    assert body["moderation_removed"] is True

    assert client.get("/api/listings").json() == []
    assert client.get(f"/api/listings/{listing_id}").status_code == 404
    with Session() as db:
        row = db.get(models.Listing, listing_id)
        # Satır silinmez; karar POST /api/admin/listing/{id}/restore ile geri
        # alınır (bkz. test_ilan_remove_sonra_restore_yayina_doner).
        assert row is not None
        assert row.moderation_removed is True
        assert row.reviewed_by == admin["id"]


def test_mesaj_remove_satiri_silmez_icerigi_sabitle_degistirir(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Önce şunu sorayım."},
    )
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]

    body = client.post(
        f"/api/admin/flagged/message/{msg_id}/review",
        headers=admin["headers"],
        json={"action": "remove"},
    ).json()
    assert body["content_removed"] is True
    assert body["is_flagged"] is False
    assert body["is_active"] is None

    # Satır yerinde: sohbet akışı iki mesajlı kalır, ikincisi sabit döner.
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert [r["id"] for r in rows] == [rows[0]["id"], msg_id]
    assert rows[1]["content"] == moderation.REMOVED_CONTENT

    with Session() as db:
        row = db.get(models.Message, msg_id)
        assert row is not None
        # Metin ÜZERİNE YAZILMAZ, taşınır: geri alma bunun üzerine kurulu.
        assert row.moderation_removed is True
        assert crypto.decrypt(row.original_content) == FLAGGED_MESSAGE_TEXT


def test_mesaj_clear_icerigi_korur(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]

    body = client.post(
        f"/api/admin/flagged/message/{msg_id}/review",
        headers=admin["headers"],
        json={"action": "clear"},
    ).json()
    assert body["content_removed"] is False

    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert rows[0]["content"] == FLAGGED_MESSAGE_TEXT
    assert client.get("/api/admin/flagged", headers=admin["headers"]).json() == []


def test_olmayan_icerik_incelemesi_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    for kind in ("listing", "message"):
        res = client.post(
            f"/api/admin/flagged/{kind}/9999/review",
            headers=admin["headers"],
            json={"action": "clear"},
        )
        assert res.status_code == 404, res.text


def test_gecersiz_inceleme_eylemi_422(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    res = client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "sil"},
    )
    assert res.status_code == 422, res.text


# ---------------------------------------------------------------------------
# kaldırılanı geri alma (restore)
#
# Bu bölüm ürünün "karar geri alınabilir" sözünü kanıtlar. Söz eskiden yalandı:
# is_active'i True yapan hiçbir uç yoktu, kaldırılan ilan hiçbir listede
# görünmüyordu ve mesajın metni üzerine yazıldığı için kalıcı kayboluyordu.
# ---------------------------------------------------------------------------

@pytest.fixture()
def key(monkeypatch):
    """Mesaj şifrelemesini açar (üretimdeki hâl)."""
    monkeypatch.setenv(crypto.KEY_ENV, crypto.generate_key())
    crypto.reset_cache()
    yield
    crypto.reset_cache()


def _remove(client, admin, kind, item_id, note="Kural ihlali."):
    res = client.post(
        f"/api/admin/flagged/{kind}/{item_id}/review",
        headers=admin["headers"],
        json={"action": "remove", "note": note},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_ilan_remove_sonra_restore_yayina_doner(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    _remove(client, admin, "listing", listing_id)
    assert client.get(f"/api/listings/{listing_id}").status_code == 404

    res = client.post(
        f"/api/admin/listing/{listing_id}/restore",
        headers=admin["headers"],
        json={"note": "Yanlış karar; ilan temiz."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {
        "kind": "listing",
        "id": listing_id,
        "restored": True,
        "is_active": True,
        "moderation_removed": False,
        # İkisi de yalnız mesajda anlamlı.
        "content_recoverable": None,
        "content_restored": None,
        "reviewed_by": admin["id"],
        "reviewed_at": body["reviewed_at"],
        "review_note": "Yanlış karar; ilan temiz.",
    }
    assert body["reviewed_at"] is not None

    # Genel liste, detay ucu ve sahibinin düzenlemesi geri geldi.
    assert [i["id"] for i in client.get("/api/listings").json()] == [listing_id]
    assert client.get(f"/api/listings/{listing_id}").status_code == 200
    assert [
        i["id"]
        for i in client.get(
            "/api/listings", headers=ali["headers"], params={"mine": True}
        ).json()
    ] == [listing_id]
    patched = client.patch(
        f"/api/listings/{listing_id}",
        headers=ali["headers"],
        json={"rent": 19000},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["rent"] == 19000

    with Session() as db:
        row = db.get(models.Listing, listing_id)
        assert row.is_active is True
        assert row.moderation_removed is False


def test_kaldirilan_ilan_removed_kuyrugunda_bulunur(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    _remove(client, admin, "listing", listing_id, note="Sahte ilan.")

    # İşaretli kuyruk boş (is_flagged False) — eskiden kayıt BURADA kaybolup
    # başka hiçbir yerde görünmediği için geri alma imkânsızdı.
    assert client.get("/api/admin/flagged", headers=admin["headers"]).json() == []

    rows = client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in rows] == [listing_id]
    row = rows[0]
    assert row["kind"] == "listing"
    assert row["moderation_removed"] is True
    assert row["is_active"] is False
    assert row["content"] == FLAGGED_LISTING_TEXT
    assert row["author_id"] == ali["id"]
    assert row["review_note"] == "Sahte ilan."
    assert row["reviewed_by"] == admin["id"]

    # Geri alınınca kuyruktan düşer.
    client.post(f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"])
    assert client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json() == []


def test_sahibinin_kapattigi_ilan_removed_kuyrugunda_gorunmez(client):
    """Kullanıcının kendi kararı moderasyon kuyruğuna düşmez."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    assert client.delete(
        f"/api/listings/{listing_id}", headers=ali["headers"]
    ).status_code == 204

    assert client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json() == []
    res = client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    )
    assert res.status_code == 400, res.text
    assert client.get(f"/api/listings/{listing_id}").status_code == 404


def test_sahibi_kapatmisken_remove_edilen_ilan_geri_alininca_yayina_donmez(ctx):
    """Geri alma, sahibin KENDİ kapatma kararını ezmez.

    İşaretlenmiş bir ilan sahibi tarafından kapatılsa bile inceleme
    kuyruğunda kalır (kuyruk is_flagged'a bakar, is_active'e değil). Yönetici
    oradan "kaldır" derse moderation_removed True olur. Geri alma bu ilanı
    KOŞULSUZ yayına alsaydı, sahibinin geri çektiği bir ilan onun haberi
    olmadan yeniden yayına girerdi.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )

    # Sahibi ilanı kendi kapatıyor; kayıt işaretli olduğu için kuyrukta kalıyor.
    assert client.delete(
        f"/api/listings/{listing_id}", headers=ali["headers"]
    ).status_code == 204
    pending = client.get("/api/admin/flagged", headers=admin["headers"]).json()
    assert [r["id"] for r in pending] == [listing_id]
    assert pending[0]["is_active"] is False

    removed = _remove(client, admin, "listing", listing_id)
    assert removed["is_active"] is False
    assert removed["moderation_removed"] is True

    res = client.post(
        f"/api/admin/listing/{listing_id}/restore",
        headers=admin["headers"],
        json={"note": "Karar geri alındı."},
    )
    assert res.status_code == 200, res.text
    # Yönetici kaldırması geri alındı AMA ilan yayına girmedi.
    assert res.json()["moderation_removed"] is False
    assert res.json()["is_active"] is False
    assert client.get("/api/listings").json() == []
    assert client.get(f"/api/listings/{listing_id}").status_code == 404
    assert client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json() == []

    with Session() as db:
        row = db.get(models.Listing, listing_id)
        assert row.is_active is False
        assert row.moderation_removed is False
        assert row.active_before_removal is None  # geri alınınca temizlenir


def test_yayindaki_ilan_remove_edilince_onceki_durum_yayin_olarak_saklanir(ctx):
    """Yayındayken kaldırılan ilan geri alınınca YAYINA döner."""
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    _remove(client, admin, "listing", listing_id)
    with Session() as db:
        assert db.get(models.Listing, listing_id).active_before_removal is True

    res = client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    )
    assert res.json()["is_active"] is True
    assert [i["id"] for i in client.get("/api/listings").json()] == [listing_id]


def test_iki_kez_remove_onceki_yayin_durumunu_ezmez(ctx):
    """Çift tıklama ilanın "kaldırmadan önce yayındaydı" bilgisini bozmamalı.

    İkinci "remove" çağrısında ilan zaten pasiftir; bayrak kontrolü olmasaydı
    active_before_removal False'a düşer ve geri alma ilanı yayına getiremezdi.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    _remove(client, admin, "listing", listing_id)
    _remove(client, admin, "listing", listing_id, note="ikinci tıklama")
    with Session() as db:
        assert db.get(models.Listing, listing_id).active_before_removal is True

    res = client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    )
    assert res.json()["is_active"] is True


def test_eski_kayitta_onceki_durum_bilinmiyorsa_restore_yayina_alir(ctx):
    """active_before_removal NULL: sütun eklenmeden önce kaldırılmış kayıt.

    Önceki durum gerçekten bilinmiyor; geri alma eski davranışa (yayına al)
    düşer ve bunu yanıtta da açıkça bildirir.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    with Session() as db:
        row = db.get(models.Listing, listing_id)
        row.is_active = False
        row.moderation_removed = True
        row.active_before_removal = None  # eski şemadan gelen kayıt
        db.commit()

    res = client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["is_active"] is True
    assert [i["id"] for i in client.get("/api/listings").json()] == [listing_id]


def test_mesaj_remove_sonra_restore_orijinal_metni_geri_getirir(ctx, key):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]

    # Şifreleme gerçekten açık: satır düz metin tutmuyor.
    with Session() as db:
        assert crypto.is_encrypted(db.get(models.Message, msg_id).content)

    _remove(client, admin, "message", msg_id)
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert rows[0]["content"] == moderation.REMOVED_CONTENT

    # Kaldırılmış mesajın ASIL metni yönetici kuyruğunda okunabiliyor;
    # yönetici neyi geri alacağını görmeden karar veremez.
    removed = client.get(
        "/api/admin/flagged?kind=message&status=removed", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in removed] == [msg_id]
    assert removed[0]["content"] == FLAGGED_MESSAGE_TEXT

    body = client.post(
        f"/api/admin/message/{msg_id}/restore",
        headers=admin["headers"],
        json={"note": "Hakaret değil, alıntı."},
    ).json()
    assert body["restored"] is True
    assert body["content_restored"] is True
    assert body["moderation_removed"] is False
    assert body["is_active"] is None
    assert body["review_note"] == "Hakaret değil, alıntı."

    # ORİJİNAL METİN BİREBİR geri geldi ve yeniden şifreli saklanıyor.
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert [r["content"] for r in rows] == [FLAGGED_MESSAGE_TEXT]
    with Session() as db:
        row = db.get(models.Message, msg_id)
        assert crypto.is_encrypted(row.content)
        assert crypto.decrypt(row.content) == FLAGGED_MESSAGE_TEXT
        assert row.original_content is None
        assert row.moderation_removed is False


def test_mesaj_restore_notsuz_govdesiz_de_calisir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]
    _remove(client, admin, "message", msg_id)

    res = client.post(
        f"/api/admin/message/{msg_id}/restore", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["review_note"] is None
    assert res.json()["content_restored"] is True


def test_iki_kez_remove_orijinal_metni_ezmez(client):
    """Çift tıklama sabiti original_content'e yazsaydı metin kaybolurdu."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]

    _remove(client, admin, "message", msg_id)
    _remove(client, admin, "message", msg_id)

    body = client.post(
        f"/api/admin/message/{msg_id}/restore", headers=admin["headers"]
    ).json()
    assert body["content_restored"] is True
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert rows[0]["content"] == FLAGGED_MESSAGE_TEXT


def test_yayindaki_kayda_restore_400(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    # DİKKAT: _matched_pair Ali'yi kendisi kaydeder; önceden ayrıca kaydetmek
    # ikinci kaydı "e-posta zaten var" yoluna düşürür ve dev_code dönmez.
    ali, ayse, match_id = _matched_pair(client)
    listing_id = _make_listing(client, ali["headers"])
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Merhaba"},
    ).json()["id"]

    for kind, item_id in (("listing", listing_id), ("message", msg_id)):
        res = client.post(
            f"/api/admin/{kind}/{item_id}/restore", headers=admin["headers"]
        )
        assert res.status_code == 400, res.text
        assert "zaten yayında" in res.json()["detail"]

    # "clear" ile incelenmiş kayıt da kaldırılmış sayılmaz.
    client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "clear"},
    )
    assert client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    ).status_code == 400


def test_ikinci_restore_400(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    _remove(client, admin, "listing", listing_id)
    assert client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    ).status_code == 200
    assert client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    ).status_code == 400


def test_olmayan_icerigi_restore_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    for kind in ("listing", "message"):
        res = client.post(f"/api/admin/{kind}/9999/restore", headers=admin["headers"])
        assert res.status_code == 404, res.text


def test_gecersiz_restore_turu_422(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    res = client.post("/api/admin/kullanici/1/restore", headers=admin["headers"])
    assert res.status_code == 422, res.text


# ---------------------------------------------------------------------------
# yönetici veri asgarisi
# ---------------------------------------------------------------------------

def test_kullanici_listesi_suspended_filtresi_zorunlu(client):
    """Filtresiz çağrı tüm kullanıcı tabanını e-postalarıyla döküyordu."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _make_user(client, "ali@uni.edu.tr", "Ali")
    assert client.get(
        "/api/admin/users", headers=admin["headers"]
    ).status_code == 422


def test_eposta_yalnizca_askidakiler_icin_doner(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    aktifler = client.get(
        "/api/admin/users?suspended=false", headers=admin["headers"]
    ).json()
    assert {u["id"] for u in aktifler} == {admin["id"], ali["id"]}
    assert all(u["email"] is None for u in aktifler)
    # Karar için gereken alanlar yerinde; kaybolan yalnızca e-posta.
    assert {u["name"] for u in aktifler} == {"Yönetici", "Ali"}

    suspended = client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Spam"},
    ).json()
    assert suspended["email"] == "ali@uni.edu.tr"

    askidakiler = client.get(
        "/api/admin/users?suspended=true", headers=admin["headers"]
    ).json()
    assert [u["email"] for u in askidakiler] == ["ali@uni.edu.tr"]

    # Askı kalkınca e-posta yeniden gizlenir.
    body = client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    ).json()
    assert body["email"] is None


# ---------------------------------------------------------------------------
# geri almanın DÜRÜSTLÜĞÜ: yanıt, gerçekte ne olduğunu söyler
# ---------------------------------------------------------------------------

def test_removed_kuyrugu_geri_alinca_ne_olacagini_bildirir(client):
    """FlaggedOut.active_before_removal — "geri alırsan yayına girer mi".

    Kaldırılanlar kuyruğunda yönetici, geri alma düğmesine basmadan ÖNCE
    kararının sonucunu görebilmeli. Bu alan olmadan iki farklı ilan (biri
    yayındayken kaldırılmış, biri sahibi kapatmışken) kuyrukta birebir aynı
    görünüyordu.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    yayinda = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    kapali = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT, title="İkinci ilan"
    )
    client.delete(f"/api/listings/{kapali}", headers=ali["headers"])

    _remove(client, admin, "listing", yayinda)
    _remove(client, admin, "listing", kapali)

    rows = {
        r["id"]: r
        for r in client.get(
            "/api/admin/flagged?status=removed", headers=admin["headers"]
        ).json()
    }
    assert rows[yayinda]["active_before_removal"] is True
    assert rows[kapali]["active_before_removal"] is False
    # İkisinin de şu anki durumu aynı; ayrımı yalnızca yeni alan taşıyor.
    assert rows[yayinda]["is_active"] is False
    assert rows[kapali]["is_active"] is False


def test_mesaj_satirinda_active_before_removal_none(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]
    _remove(client, admin, "message", msg_id)

    rows = client.get(
        "/api/admin/flagged?kind=message&status=removed", headers=admin["headers"]
    ).json()
    assert rows[0]["active_before_removal"] is None


def test_content_restored_metin_okunamiyorsa_false_doner(ctx, key, monkeypatch):
    """content_restored, alanın DOLU olduğunu değil OKUNABİLDİĞİNİ söyler.

    Anahtar kaybolur ya da dönerse geri konan içerik crypto.UNREADABLE olarak
    çözülür. Eskiden yalnızca "original_content dolu mu" bakılıyordu; yanıt
    content_restored:True diyor, arayüz "Mesajın metni geri kondu." basıyor,
    kullanıcı ise [unreadable] görüyordu.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]
    _remove(client, admin, "message", msg_id)

    # Anahtar değişti: saklanan şifreli metin artık çözülemiyor.
    monkeypatch.setenv(crypto.KEY_ENV, crypto.generate_key())
    crypto.reset_cache()

    body = client.post(
        f"/api/admin/message/{msg_id}/restore", headers=admin["headers"]
    ).json()
    assert body["restored"] is True
    assert body["content_recoverable"] is True  # metin saklanmıştı
    assert body["content_restored"] is False  # ama okunamıyor
    assert body["moderation_removed"] is False

    # Kullanıcının gördüğü de bunu doğruluyor.
    rows = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert rows[0]["content"] == crypto.UNREADABLE


def test_metni_kurtarilamayan_mesaj_restore_sonrasi_kuyrukta_kalir(ctx):
    """original_content NULL: sütun eklenmeden önce kaldırılmış kayıt.

    Eskiden restore metni geri koymadan moderation_removed'ı False yapıyordu.
    Sonuç: kayıt Kaldırılanlar kuyruğundan düşüyor, kullanıcı hâlâ
    "kaldırıldı" görüyor, ikinci restore 400 veriyor ve kayıt HİÇBİR uçtan
    bulunamıyordu — "kaldırılan içerik BULUNABİLİR kalır" ilkesinin tersi.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Merhaba"},
    ).json()["id"]
    with Session() as db:
        row = db.get(models.Message, msg_id)
        row.content = moderation.REMOVED_CONTENT
        row.original_content = None  # eski şemadan gelen kayıt
        row.moderation_removed = True
        row.reviewed_by = admin["id"]
        row.review_note = "Kaldırma notu"
        db.commit()

    res = client.post(
        f"/api/admin/message/{msg_id}/restore",
        headers=admin["headers"],
        json={"note": "geri alalım"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["restored"] is False
    assert body["content_recoverable"] is False
    assert body["content_restored"] is False
    assert body["moderation_removed"] is True
    # Gerçekleşmemiş bir geri alma, kaldırma kararının izini EZMEZ.
    assert body["review_note"] == "Kaldırma notu"

    # Kayıt hâlâ bulunabilir ve tekrar denenebilir (ikinci çağrı da 400 değil).
    removed = client.get(
        "/api/admin/flagged?kind=message&status=removed", headers=admin["headers"]
    ).json()
    assert [r["id"] for r in removed] == [msg_id]
    assert client.post(
        f"/api/admin/message/{msg_id}/restore", headers=admin["headers"]
    ).status_code == 200

    with Session() as db:
        row = db.get(models.Message, msg_id)
        assert row.moderation_removed is True
        assert row.review_note == "Kaldırma notu"


def test_kaldirilmis_icerige_clear_reddedilir(ctx):
    """clear İŞARETİ temizler, KALDIRMAYI değil.

    Eskiden kabul ediliyordu ve tutarsız bir durum bırakıyordu:
    moderation_removed True kalırken yanıt content_removed:False dönüyor,
    üstelik kaldırma kararının reviewed_at izi de üzerine yazılıyordu.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, match_id = _matched_pair(client)
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT, title="Üçüncü ilan"
    )
    msg_id = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": FLAGGED_MESSAGE_TEXT},
    ).json()["id"]
    _remove(client, admin, "listing", listing_id, note="Kaldırma notu")
    _remove(client, admin, "message", msg_id, note="Kaldırma notu")

    for kind, item_id in (("listing", listing_id), ("message", msg_id)):
        res = client.post(
            f"/api/admin/flagged/{kind}/{item_id}/review",
            headers=admin["headers"],
            json={"action": "clear", "note": "yanlışlıkla"},
        )
        assert res.status_code == 400, res.text
        assert "restore" in res.json()["detail"]

    # Hiçbir şey değişmedi: kayıtlar hâlâ kaldırılmış ve kuyrukta.
    with Session() as db:
        assert db.get(models.Listing, listing_id).moderation_removed is True
        assert db.get(models.Listing, listing_id).review_note == "Kaldırma notu"
        assert db.get(models.Message, msg_id).moderation_removed is True
    removed = client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json()
    assert {r["id"] for r in removed} == {listing_id, msg_id}


# ---------------------------------------------------------------------------
# askının kaldırılması da bir eylemdir (ilke 4)
# ---------------------------------------------------------------------------

def test_unsuspend_iz_birakir(client):
    """Askı kalkınca gerekçe SİLİNMEZ, geçmişe taşınır; kaldıran yazılır.

    Eskiden bütün suspended_* alanları NULL'a çekiliyordu: hesabın daha önce
    askıya alınıp alınmadığı, gerekçesi ve askıyı kimin kaldırdığı hiçbir
    yerden okunamıyordu.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Tekrarlayan spam"},
    )
    body = client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    ).json()

    assert body["is_suspended"] is False
    # Yürürlükteki alanlar temiz — aktif hesapta askı gerekçesi gösterilmez.
    assert body["suspended_reason"] is None
    assert body["suspended_at"] is None
    assert body["suspended_by"] is None
    # Ama geçmiş duruyor.
    assert body["last_suspension_reason"] == "Tekrarlayan spam"
    assert body["unsuspended_by"] == admin["id"]
    assert body["unsuspended_at"] is not None

    # Aktif kullanıcı listesinden de okunabiliyor.
    aktifler = {
        u["id"]: u
        for u in client.get(
            "/api/admin/users?suspended=false", headers=admin["headers"]
        ).json()
    }
    assert aktifler[ali["id"]]["last_suspension_reason"] == "Tekrarlayan spam"


def test_yeniden_askiya_alinca_kaldirma_izi_temizlenir(client):
    """Yürürlükteki askı ile geçmişteki kaldırma karışmamalı."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Birinci"},
    )
    client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    )
    body = client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "İkinci"},
    ).json()

    assert body["is_suspended"] is True
    assert body["suspended_reason"] == "İkinci"
    assert body["unsuspended_at"] is None
    assert body["unsuspended_by"] is None
    # Gerekçe geçmişi silinmez.
    assert body["last_suspension_reason"] == "Birinci"


def test_askida_olmayan_kullaniciya_unsuspend_iz_uydurmaz(client):
    """Zaten aktif hesaba unsuspend, olmamış bir askıyı kaydetmemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    body = client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    ).json()
    assert body["unsuspended_at"] is None
    assert body["unsuspended_by"] is None
    assert body["last_suspension_reason"] is None
