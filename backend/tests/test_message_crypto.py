"""Mesaj şifreleme: gidiş-dönüş, geriye dönük uyum ve uçtaki davranış.

Not: bu şifreleme sunucuda saklanan veriyi korur (at-rest); anahtar sunucuda
olduğu için uçtan uca değildir.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crypto, models
from app.db import Base, get_db
from app.main import app


@pytest.fixture()
def key(monkeypatch):
    """Süreç boyunca önbelleklenen anahtarı test için ayarlar."""
    monkeypatch.setenv(crypto.KEY_ENV, crypto.generate_key())
    crypto.reset_cache()
    yield
    crypto.reset_cache()


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


# ---- birim ----

def test_gidis_donus_kayipsiz(key):
    assert crypto.key_available() is True
    for text in ["Merhaba", "Türkçe karakterler: şğüıöç", "emoji 🏠", "a" * 2000]:
        blob = crypto.encrypt(text)
        assert blob.startswith(crypto.PREFIX)
        assert crypto.decrypt(blob) == text


def test_ayni_metin_farkli_sifreli_deger(key):
    # Her yazımda yeni nonce üretilir; aynı metin aynı kaydı vermez.
    assert crypto.encrypt("selam") != crypto.encrypt("selam")


def test_eski_duz_metin_oldugu_gibi_doner(key):
    assert crypto.decrypt("eski düz metin mesaj") == "eski düz metin mesaj"
    assert crypto.is_encrypted("eski düz metin mesaj") is False


def test_anahtar_yoksa_duz_metin(monkeypatch):
    monkeypatch.delenv(crypto.KEY_ENV, raising=False)
    crypto.reset_cache()
    try:
        assert crypto.key_available() is False
        assert crypto.encrypt("selam") == "selam"
        assert crypto.decrypt("selam") == "selam"
    finally:
        crypto.reset_cache()


def test_bozuk_kayit_istisna_firlatmaz(key):
    assert crypto.decrypt(crypto.PREFIX + "bozuk-veri") == crypto.UNREADABLE


def test_farkli_uyarilar_birbirini_bastirmaz(monkeypatch, capsys):
    """Uyarı bayrağı mesaj başına tutulur.

    Eskiden tek global bayrak vardı: "MESSAGE_KEY tanımlı değil" basıldıktan
    sonra "mesaj çözülemedi" uyarısı hiç loglanmıyordu.
    """
    monkeypatch.delenv(crypto.KEY_ENV, raising=False)
    crypto.reset_cache()
    try:
        # 1. uyarı: anahtar yok
        assert crypto.encrypt("selam") == "selam"
        # 2. uyarı (farklı): şifreli kayıt var ama anahtar yok
        assert crypto.decrypt(crypto.PREFIX + "abc") == crypto.UNREADABLE
        out = capsys.readouterr().out
        assert crypto.KEY_ENV in out
        assert "okunamıyor" in out
    finally:
        crypto.reset_cache()


def test_ayni_uyari_bir_kez_basilir(key, capsys):
    crypto.decrypt(crypto.PREFIX + "bozuk-1")
    capsys.readouterr()  # ilk uyarıyı yut
    crypto.decrypt(crypto.PREFIX + "bozuk-2")
    assert capsys.readouterr().out == ""


def test_okunamaz_sabiti_dilden_bagimsiz():
    """Arayüz bu işareti tanıyıp kendi dilinde çevirir; Türkçe metin olmamalı."""
    assert crypto.UNREADABLE == "[unreadable]"
    assert crypto.UNREADABLE.isascii()


def test_genkey_32_bayt():
    import base64

    assert len(base64.b64decode(crypto.generate_key())) == crypto.KEY_BYTES


# ---- uç davranışı ----

def _make_user(client, email, name):
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    body = client.post(
        "/api/auth/verify-otp",
        json={"email": email, "code": res.json()["dev_code"]},
    ).json()
    headers = {"Authorization": f"Bearer {body['token']}"}
    client.patch("/api/auth/me", headers=headers, json={"name": name})
    return {"id": body["user"]["id"], "headers": headers}


def _matched_pair(client):
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing = client.post(
        "/api/listings",
        headers=ali["headers"],
        json={
            "type": "ev_ilani",
            "title": "Ali'nin evi",
            "description": "Geniş ve aydınlık.",
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


def test_mesaj_veritabaninda_sifreli_apide_duz(key, ctx):
    client, Session = ctx
    ali, ayse, match_id = _matched_pair(client)

    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Ev hâlâ müsait mi?"},
    )
    assert res.status_code == 201, res.text
    # Yanıt düz metin döner
    assert res.json()["content"] == "Ev hâlâ müsait mi?"

    # Ham kayıt şifreli
    with Session() as db:
        row = db.get(models.Message, res.json()["id"])
    assert row.content.startswith(crypto.PREFIX)
    assert "müsait" not in row.content

    # Listeleme de düz metin döner
    msgs = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert [m["content"] for m in msgs] == ["Ev hâlâ müsait mi?"]

    # Eşleşme listesindeki önizleme de çözülür
    matches = client.get("/api/matches", headers=ayse["headers"]).json()
    assert matches[0]["last_message"] == "Ev hâlâ müsait mi?"


def test_eski_duz_metin_satir_okunabilir(key, ctx):
    """Anahtar açılmadan önce yazılmış kayıtlar okunmaya devam etmeli."""
    client, Session = ctx
    ali, ayse, match_id = _matched_pair(client)

    with Session() as db:
        db.add(
            models.Message(
                match_id=match_id, sender_id=ali["id"], content="şifresiz eski mesaj"
            )
        )
        db.commit()

    client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "yeni mesaj"},
    )

    msgs = client.get(
        f"/api/matches/{match_id}/messages", headers=ali["headers"]
    ).json()
    assert [m["content"] for m in msgs] == ["şifresiz eski mesaj", "yeni mesaj"]


# ---- anahtar biçimleri ----
# Render blueprint'i MESSAGE_KEY'i `generateValue: true` ile üretir; bu değer
# base64(32 bayt) DEĞİLDİR. Eskiden reddedilip sessizce düz metne düşülüyordu.


def test_render_tarzi_ham_dize_anahtari_kabul_edilir(monkeypatch):
    monkeypatch.setenv("MESSAGE_KEY", "aB3xY7kLmN2pQ8rS4tU6vW9zC1dE5fG0")  # 32 karakter
    crypto.reset_cache()

    blob = crypto.encrypt("gizli")
    assert blob.startswith(crypto.PREFIX)
    assert crypto.decrypt(blob) == "gizli"


def test_base64_32_bayt_anahtari_kabul_edilir(monkeypatch):
    monkeypatch.setenv("MESSAGE_KEY", crypto.generate_key())
    crypto.reset_cache()

    blob = crypto.encrypt("gizli")
    assert blob.startswith(crypto.PREFIX)
    assert crypto.decrypt(blob) == "gizli"


def test_kisa_anahtar_reddedilir(monkeypatch):
    """Zayıf bir değer sessizce anahtara dönüşmemeli — düz metin yazılır."""
    monkeypatch.setenv("MESSAGE_KEY", "kisa-parola")
    crypto.reset_cache()

    assert not crypto.encrypt("gizli").startswith(crypto.PREFIX)
