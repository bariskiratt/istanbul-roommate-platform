"""İçerik denetimi: kural katmanı ve uçlara bağlanışı.

Yanlış pozitif testleri kasıtlı olarak geniş: "sıkıntı", "sık sık", "kanka"
gibi masum kelimeler yüzünden ilan açılamaması, kaçırılan bir küfürden çok
daha ağır bir hata olur.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models, moderation
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


def _auth_headers(client, email="ali@uni.edu.tr") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _listing(**overrides) -> dict:
    return {
        "type": "ev_ilani",
        "title": "Kadıköy'de güneşli 2+1",
        "description": "Moda'ya 5 dakika, geniş salon.",
        "district": "Kadıköy",
        "photos": [],
        "rent": 18000,
        "room_count": "2+1",
    } | overrides


# ---- kural katmanı (birim) ----

CLEAN_TEXTS = [
    "Kadıköy'de güneşli 2+1, Moda'ya 5 dakika yürüme mesafesinde.",
    "Sıkıntı yok, ev sıcak ve ışık alıyor; sık sık temizlik yapıyoruz.",
    "Kanka gel bir bak, amaç uyumlu bir ev arkadaşı bulmak.",
    "3+1 daire, kira 51k TL, aidat dahil. 2024 2025 2026 yılları boyunca.",
    "Sıkışık bir bütçem var ama düzenli biriyim.",
]


@pytest.mark.parametrize("text", CLEAN_TEXTS)
def test_temiz_metin_gecer(text):
    for kind in ("listing", "message"):
        result = moderation.check_rules(text, kind=kind)
        assert result.action == "allow", (kind, result.reasons)


# Kural sözlüklerine "yakın geçen" ama tamamen masum ilan cümleleri.
# Hepsi bir zamanlar yanlışlıkla engelleniyordu; bir daha engellenmemeli.
INNOCENT_TEXTS = [
    # "fuk" kökü → "fukara"
    "Fukara öğrenciyiz, uygun fiyatlı ev arıyoruz.",
    # "sadece (turk|beyaz)" kalıbı
    "Sadece Türkçe konuşuyorum, İngilizcem zayıf.",
    "Mutfakta sadece beyaz eşya var, mobilya yok.",
    # ödeme/aciliyet kelimeleri Türkiye'de olağan kira dilidir
    "Kira ve depozito havale ile ödenebilir, acil kiracı aranıyor.",
    "Depozito EFT ile alınır.",
    "Papara ile ödeme yapabilirim.",
    # "çıplak" masum kullanımı
    "Çıplak duvarlar var, boyanacak.",
    # "cunt" kökü → "cunta"
    "Cunta dönemi tarihi üzerine tez yazıyorum.",
    # "kodumun" → yazılımcı için olağan
    "Kodumun içinde hata var, yazılımcıyım.",
    # "manyak" pekiştireç olarak
    "Manyak güzel bir daire, deniz manzaralı.",
]


@pytest.mark.parametrize("text", INNOCENT_TEXTS)
def test_masum_ilan_cumlesi_engellenmez(text):
    """Masum bir ilanı engellemek, kaba bir sözü kaçırmaktan daha kötüdür."""
    for kind in ("listing", "message"):
        result = moderation.check_rules(text, kind=kind)
        assert result.action != "block", (kind, result.reasons)
        # Bugün hiçbiri işaretlenmiyor da; gerileme olursa görelim.
        assert result.action == "allow", (kind, result.reasons)


# Kelime aralarını yok sayan ("sıkıştırılmış") aramanın yanlış pozitif
# üretmediğini gösteren cümleler: birleşince küfür köklerine benzeyebilirler.
JOINED_SAFE_TEXTS = [
    "Çok amaçlı salon ve geniş balkon var.",
    "Ders çalışma masası ve kitaplık mevcut.",
    "Banyo ve tuvalet ayrı, kombi yeni.",
    "Daire çok şık, ışıklı ve ferah.",
    # Türkçe karakter katlaması "şıktır" → "siktir" üretiyordu.
    "Daire oldukça şıktır, salon ışıktır ve ferahtır.",
    "Şık tıraş makinesi ve saç kurutma makinesi var.",
    "Mutfakta kısık ateşte yemek yapıyoruz, sebzeleri doğrarım.",
    "Şeref sizin olsun, ev tutuldu.",
    "Sıkı sıkıya bağlı bir ev arkadaşı grubu değiliz.",
    "Ananas dilimledim, seksen metrekare salon.",
]


@pytest.mark.parametrize("text", JOINED_SAFE_TEXTS)
def test_sikistirilmis_arama_yanlis_pozitif_uretmez(text):
    for kind in ("listing", "message"):
        result = moderation.check_rules(text, kind=kind)
        assert result.action == "allow", (kind, result.reasons)


@pytest.mark.parametrize(
    "text",
    [
        "siktir git buradan",
        "orospu çocuğu ilan sahibi",
        "amk ne biçim ev",
        "you are a fucking bastard",
        "s1kt1r git",
    ],
)
def test_kufur_engellenir(text):
    result = moderation.check_rules(text, kind="message")
    assert result.action == "block"
    assert any(r.startswith(moderation.KUFUR) for r in result.reasons)


@pytest.mark.parametrize(
    ("text", "prefix"),
    [
        # kelimeyi parçalara bölme
        ("oros pu çocuğu", moderation.KUFUR),
        # homoglif: Kiril "о" (U+043E)
        ("оrospu çocuğu", moderation.KUFUR),
        # sıfır genişlikli boşluk (U+200B)
        ("or​ospu çocuğu", moderation.KUFUR),
        # tehdidin parçalanmış hâli
        ("seni geber tirim", moderation.TACIZ),
    ],
)
def test_kacis_denemeleri_engellenir(text, prefix):
    result = moderation.check_rules(text, kind="message")
    assert result.action == "block", result.reasons
    assert any(r.startswith(prefix) for r in result.reasons)


@pytest.mark.parametrize(
    "text",
    [
        "s.i.k.t.i.r",
        "s i k t i r",
        "ＳＩＫＴＩＲ git",  # fullwidth
        "siiiktir git",  # harf tekrarı
    ],
)
def test_bilinen_kacislar_calismaya_devam_ediyor(text):
    assert moderation.check_rules(text, kind="message").action == "block"


def test_hafif_hakaret_isaretlenir_engellenmez():
    result = moderation.check_rules("aptal herif", kind="message")
    assert result.action == "flag"
    assert any(r.startswith(moderation.HAKARET) for r in result.reasons)


def test_dolandiricilik_kaliplari_yakalanir():
    """Dolandırıcılık şüphesi işaretlenir ama ASLA engellenmez.

    Tespit olasılıksaldır ("depozito havale ile alınır" masum bir cümledir),
    bu yüzden yalnızca yönetici incelemesine düşer.
    """
    unseen = moderation.check_rules(
        "Evi görmeden kapora gönder, anahtarı kargoyla yollarım.", kind="listing"
    )
    assert unseen.action == "flag"
    assert any(r.startswith(moderation.DOLANDIRICILIK) for r in unseen.reasons)

    iban = moderation.check_rules(
        "Acil! TR33 0006 1005 1978 6457 8413 26 hesabıma depozito yatır.",
        kind="listing",
    )
    assert iban.action == "flag"
    assert any(r.startswith(moderation.DOLANDIRICILIK) for r in iban.reasons)


def test_telefon_ilanda_isaretlenir_mesajda_isaretlenmez():
    text = "Detaylar için ara: 0532 123 45 67"

    listing = moderation.check_rules(text, kind="listing")
    assert listing.action == "flag"
    assert f"{moderation.ILETISIM}:telefon" in listing.reasons

    # Sohbette numara paylaşmak normaldir.
    assert moderation.check_rules(text, kind="message").action == "allow"


def test_hicbir_dolandiricilik_kalibi_engellemez():
    """Kategorinin tavanı `block` eşiğinin altında kalmalı."""
    assert moderation._SCAM_MAX < moderation.BLOCK_THRESHOLD
    for text in (
        "Acil! Hemen para gönder, hesabıma yatır, kaporayı bugün son.",
        "Yurt dışındayım, evi göremezsiniz; depozitoyu havale et, "
        "anahtarı kargoyla gönderirim.",
        "Whatsapp'tan yaz, kaporayı hemen papara ile gönder.",
    ):
        result = moderation.check_rules(text, kind="listing")
        assert result.action != "block", (text, result.reasons)


def test_ayrimcilik_kalibi_isaretlenir_engellenmez():
    """Ayrımcılık şüphesi sezgiseldir: en fazla işaretlenir."""
    for text in ("Sadece Türk kiracı alıyoruz.", "Suriyeli istemiyoruz."):
        result = moderation.check_rules(text, kind="listing")
        assert result.action == "flag", (text, result.reasons)
        assert any(r.startswith(moderation.NEFRET) for r in result.reasons)


def test_acik_nefret_ifadesi_engellenir():
    result = moderation.check_rules("zenci istemiyorum", kind="listing")
    assert result.action == "block"
    assert any(r.startswith(moderation.NEFRET) for r in result.reasons)


def test_describe_turkce_cumle_uretir():
    text = moderation.describe([f"{moderation.KUFUR}:siktir"])
    assert "küfür" in text


# ---- ilan ucu ----

def test_ilan_kufur_iceriyorsa_422(ctx):
    client, _ = ctx
    headers = _auth_headers(client)
    res = client.post(
        "/api/listings",
        headers=headers,
        json=_listing(description="Beğenmeyen siktir gitsin."),
    )
    assert res.status_code == 422, res.text
    assert "küfür" in res.json()["detail"]


def test_ilan_temizse_isaretlenmez(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    assert client.post(
        "/api/listings", headers=headers, json=_listing()
    ).status_code == 201

    with Session() as db:
        row = db.scalar(select(models.Listing))
    assert row.is_flagged is False


def test_ilan_iletisim_bilgisi_isaretlenir_ama_yayinlanir(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    res = client.post(
        "/api/listings",
        headers=headers,
        json=_listing(description="Detaylar için ara: 0532 123 45 67"),
    )
    assert res.status_code == 201, res.text

    with Session() as db:
        row = db.get(models.Listing, res.json()["id"])
    assert row.is_flagged is True
    # İşaretli ilan yine de listede görünür (yönetici incelemesine düşer).
    assert [i["id"] for i in client.get("/api/listings").json()] == [row.id]


def test_ilan_guncellemesi_de_denetlenir(ctx):
    client, Session = ctx
    headers = _auth_headers(client)
    listing_id = client.post(
        "/api/listings", headers=headers, json=_listing()
    ).json()["id"]

    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": "Aramayın, orospu çocuğu istemiyorum."},
    )
    assert res.status_code == 422

    # Temiz güncelleme geçer, işaret kalmaz
    assert client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": "Ev eşyalı, ulaşım çok rahat."},
    ).status_code == 200
    with Session() as db:
        assert db.get(models.Listing, listing_id).is_flagged is False


# ---- mesaj ucu ----

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


def matched_pair(client):
    """Ali + Ayşe'yi eşleştirir, (ali, ayse, match_id) döner."""
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing = client.post(
        "/api/listings", headers=ali["headers"], json=_listing()
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


def test_mesajda_kufur_engellenir(ctx):
    client, _ = ctx
    ali, _, match_id = matched_pair(client)
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "siktir git"},
    )
    assert res.status_code == 422, res.text
    assert "küfür" in res.json()["detail"]


def test_mesajda_telefon_paylasimi_serbest(ctx):
    client, Session = ctx
    ali, _, match_id = matched_pair(client)
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Numaram 0532 123 45 67, arayabilirsin."},
    )
    assert res.status_code == 201, res.text

    with Session() as db:
        row = db.get(models.Message, res.json()["id"])
    assert row.is_flagged is False


def test_mesajda_hakaret_isaretlenir_ama_iletilir(ctx):
    client, Session = ctx
    ali, ayse, match_id = matched_pair(client)
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Bence bu fiyat aptalca."},
    )
    assert res.status_code == 201, res.text

    with Session() as db:
        assert db.get(models.Message, res.json()["id"]).is_flagged is True

    msgs = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert msgs[-1]["content"] == "Bence bu fiyat aptalca."


# ---- sistem sabitlerinin taklidi ----

def test_sistem_sabitleri_tek_kaynaktan_okunuyor():
    """Sabit iki yerde yazılırsa biri değişince arayüzün çevirisi bozulur.

    crypto.UNREADABLE ve moderation.REMOVED_CONTENT sunucunun ürettiği,
    dilden bağımsız işaretlerdir; arayüz onları tanıyıp kendi dilinde bir
    karşılık basar. SYSTEM_MARKERS bu iki sabitin KENDİSİNİ taşımalı,
    kopyasını değil.
    """
    from app import crypto

    assert crypto.UNREADABLE in moderation.SYSTEM_MARKERS
    assert moderation.REMOVED_CONTENT in moderation.SYSTEM_MARKERS
    assert len(set(moderation.SYSTEM_MARKERS)) == len(moderation.SYSTEM_MARKERS)
    # admin.py de aynı kaynaktan okumalı.
    from app import admin

    assert admin.REMOVED_CONTENT is moderation.REMOVED_CONTENT


@pytest.mark.parametrize("marker", moderation.SYSTEM_MARKERS)
def test_is_system_marker_tam_esitlik_arar(marker):
    assert moderation.is_system_marker(marker)
    assert moderation.is_system_marker(f"  {marker}\n")
    assert moderation.is_system_marker(marker.upper())
    # Cümle içinde geçmesi masumdur; arayüz de tam eşitlik arıyor.
    assert not moderation.is_system_marker(f"şu yazıyor: {marker}")
    assert not moderation.is_system_marker(marker.strip("[]"))
    assert not moderation.is_system_marker("")
    assert not moderation.is_system_marker(None)


@pytest.mark.parametrize("marker", moderation.SYSTEM_MARKERS)
def test_ilanda_sistem_sabiti_reddedilir(ctx, marker):
    """İlan açıklaması yönetici kuyruğunda olduğu gibi gösteriliyor."""
    client, _ = ctx
    headers = _auth_headers(client)
    res = client.post(
        "/api/listings", headers=headers, json=_listing(description=marker)
    )
    assert res.status_code == 422, res.text
    assert marker not in res.json()["detail"]

    # Başlıkta da yasak (min_length=3 olduğu için sabitler zaten yeterince uzun).
    assert client.post(
        "/api/listings", headers=headers, json=_listing(title=marker)
    ).status_code == 422


def test_ilan_guncellemesiyle_de_sistem_sabiti_yazilamaz(ctx):
    client, _ = ctx
    headers = _auth_headers(client)
    listing_id = client.post(
        "/api/listings", headers=headers, json=_listing()
    ).json()["id"]

    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"description": moderation.REMOVED_CONTENT},
    )
    assert res.status_code == 422, res.text
    assert client.get(f"/api/listings/{listing_id}").json()["description"] == (
        _listing()["description"]
    )
