"""Yöneticinin YIKICI ve DÜZELTİCİ yetkileri — /api/admin/*.

Kapsam:
  - DELETE /api/admin/listings/{id}        ilanı KALICI silme
  - PATCH  /api/admin/listings/{id}        başkasının ilanını düzenleme
  - POST   /api/admin/listings/{id}/publish sahibinin kapattığı ilanı açma
  - DELETE /api/admin/users/{id}           hesabı KALICI silme
  - GET    /api/admin/listings             tüm ilanlar + arama + durum süzgeci
  - GET    /api/admin/users?q=             kullanıcı arama
  - GET    /api/admin/actions              denetim kaydı

Bu dosyanın asıl derdi üç söz:
  1. İLAN SİLİNİR AMA SOHBET YAŞAR. Eşleşme bir ilan üzerinden kurulur;
     ilanı silmek insanların birbirine yazdıklarını silmez.
  2. GERİ ALINAMAZ HER EYLEM İZ BIRAKIR. Satır gidince "neyi neden sildim"in
     cevabı yalnızca models.AdminAction'da kalır — aktörü silinse bile.
  3. YÖNETİCİ KENDİNİ KİLİTLEYEMEZ. Son yönetici kendini silerse platformun
     yönetimi geri dönülemez biçimde kaybolur.

Yetki matrisi (401/403) test_admin.py::ADMIN_ENDPOINTS içinde.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]
# Kurulumda ikinci bir yönetici adresi tanımlı değilse o testler atlanır.
SECOND_ADMIN = sorted(ADMIN_EMAILS)[1] if len(ADMIN_EMAILS) > 1 else None

# Denetimin ENGELLEDİĞİ metin (bkz. test_moderation.py). Normal kullanıcı
# yolunda 422 verir; yönetici yolunda vermemeli.
BLOCKED_TEXT = "siktir git"
# Denetimin yalnızca İŞARETLEDİĞİ metin.
FLAGGED_LISTING_TEXT = "Detaylar için ara: 0532 123 45 67"


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
    return {
        "id": data["user"]["id"],
        "email": email,
        "name": name,
        "headers": headers,
    }


def _listing_payload(**overrides) -> dict:
    return {
        "type": "ev_ilani",
        "title": "Kadıköy'de güneşli 2+1",
        "description": "Moda'ya 5 dakika, geniş salon.",
        "district": "Kadıköy",
        "photos": [
            "https://example.com/1.jpg",
            "https://example.com/2.jpg",
            "https://example.com/3.jpg",
        ],
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
    """Ali'nin ilanı üzerinden Ali + Ayşe eşleşir.

    (ali, ayse, listing_id, match_id) döner.
    """
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
    return ali, ayse, listing_id, match_id


def _delete_listing(client, admin, listing_id, reason="Hukuki kaldırma talebi"):
    return client.request(
        "DELETE",
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"reason": reason},
    )


def _delete_user(client, admin, user_id, reason="Sahte hesap"):
    return client.request(
        "DELETE",
        f"/api/admin/users/{user_id}",
        headers=admin["headers"],
        json={"reason": reason},
    )


def _actions(client, admin, **params) -> list[dict]:
    res = client.get(
        "/api/admin/actions", headers=admin["headers"], params=params
    )
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# ilanı KALICI silme
# ---------------------------------------------------------------------------

def test_ilan_kalici_silinir_satir_gider(ctx):
    """"Kaldırma"nın aksine satır gerçekten yok olur."""
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    res = _delete_listing(client, admin, listing_id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "listing"
    assert body["id"] == listing_id
    assert body["deleted"] is True

    with Session() as db:
        assert db.get(models.Listing, listing_id) is None
    # Kaldırılanlar kuyruğunda da yok: kaldırma değil, silme yapıldı.
    kuyruk = client.get(
        "/api/admin/flagged?status=removed", headers=admin["headers"]
    ).json()
    assert all(row["id"] != listing_id for row in kuyruk if row["kind"] == "listing")


def test_ilan_silinince_sohbet_yasar(ctx):
    """EN ÖNEMLİ SÖZ: ilan gider, insanların konuşması kalır.

    matches.listing_id NULL'a çekilir; eşleşme, geçmiş mesajlar ve YENİ mesaj
    gönderme çalışmaya devam eder. Eşleşme de silinseydi bir ilanı silmek iki
    kişinin özel yazışmasını da silerdi — kimsenin istemediği bir yan etki.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, listing_id, match_id = _matched_pair(client)

    assert client.post(
        f"/api/matches/{match_id}/messages",
        headers=ayse["headers"],
        json={"content": "Merhaba, ev hâlâ müsait mi?"},
    ).status_code == 201

    assert _delete_listing(client, admin, listing_id).status_code == 200

    # 1. Eşleşme duruyor, ilan bağı koptu.
    with Session() as db:
        match = db.get(models.Match, match_id)
        assert match is not None, "ilan silinince eşleşme de silinmiş"
        assert match.listing_id is None

    # 2. Geçmiş sohbet İKİ TARAFTAN DA okunabiliyor.
    for user in (ali, ayse):
        res = client.get(
            f"/api/matches/{match_id}/messages", headers=user["headers"]
        )
        assert res.status_code == 200, res.text
        assert [m["content"] for m in res.json()] == ["Merhaba, ev hâlâ müsait mi?"]

    # 3. Yeni mesaj hâlâ gönderilebiliyor.
    res = client.post(
        f"/api/matches/{match_id}/messages",
        headers=ali["headers"],
        json={"content": "Müsait, konuşalım."},
    )
    assert res.status_code == 201, res.text
    okunan = client.get(
        f"/api/matches/{match_id}/messages", headers=ayse["headers"]
    ).json()
    assert [m["content"] for m in okunan] == [
        "Merhaba, ev hâlâ müsait mi?",
        "Müsait, konuşalım.",
    ]


def test_ilan_silme_bagli_kayitlari_temizler(ctx):
    """Kaydırmalar ve o ilana açılmış raporlar birlikte gider.

    Postgres'te swipes.listing_id kısıtı temizlenmezse silme 500 verir;
    raporlarda kısıt yok ama konusu kalmamış rapor yönetici kuyruğunda
    tıklanınca 404 veren ölü kayda dönüşür.
    """
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, listing_id, _ = _matched_pair(client)
    assert client.post(
        "/api/reports",
        headers=ayse["headers"],
        json={"target_type": "listing", "target_id": listing_id, "reason": "spam"},
    ).status_code == 201

    body = _delete_listing(client, admin, listing_id).json()
    assert body["cleanup"]["swipes"] == 1
    assert body["cleanup"]["reports"] == 1
    # SİLİNEN değil, KOPARILAN eşleşme sayısı: sohbet yaşıyor.
    assert body["cleanup"]["detached_matches"] == 1

    with Session() as db:
        assert db.scalar(
            select(func.count()).select_from(models.Swipe)
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(models.Report)
        ) == 0
        assert db.scalar(select(func.count()).select_from(models.Match)) == 1


def test_ilan_silme_denetim_kaydi_yazar(client):
    """Satır gidince geriye kalan tek şey bu kayıt."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    body = _delete_listing(
        client, admin, listing_id, reason="Üçüncü kişinin adresi paylaşılmış"
    ).json()

    kayitlar = _actions(client, admin)
    assert len(kayitlar) == 1
    kayit = kayitlar[0]
    assert kayit["id"] == body["action_id"]
    assert kayit["action"] == "listing_delete"
    assert kayit["target_type"] == "listing"
    assert kayit["target_id"] == listing_id
    assert kayit["reason"] == "Üçüncü kişinin adresi paylaşılmış"
    assert kayit["actor_id"] == admin["id"]
    assert kayit["actor_name"] == "Yönetici"
    # Silinen satırdan geriye ne kaldığı: başlık ve sahibi.
    detay = json.loads(kayit["detail"])
    assert detay["title"] == "Kadıköy'de güneşli 2+1"
    assert detay["owner_id"] == ali["id"]
    assert detay["owner_name"] == "Ali"


@pytest.mark.parametrize(
    "govde",
    [None, {}, {"reason": ""}, {"reason": "   "}],
    ids=["gövdesiz", "boş-gövde", "boş-gerekçe", "boşluk-gerekçe"],
)
def test_ilan_silme_gerekce_zorunlu(client, govde):
    """Gerekçesiz silme kabul edilmez: denetim kaydının tek açıklaması o."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    kwargs = {"headers": admin["headers"]}
    if govde is not None:
        kwargs["json"] = govde
    res = client.request("DELETE", f"/api/admin/listings/{listing_id}", **kwargs)
    assert res.status_code == 422, res.text
    # Ret gerçekten koruyucu: ilan yerinde duruyor.
    assert client.get(f"/api/listings/{listing_id}").status_code == 200


def test_olmayan_ilani_silme_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    assert _delete_listing(client, admin, 9999).status_code == 404


def test_listings_e_bakan_yabanci_anahtarlar_biliniyor():
    """listings.id'ye YENİ bir yabancı anahtar eklenirse bu test kırılır.

    Neden gerekli: purge_listing elle yazılmış bir temizlik listesi tutuyor.
    Yeni bir tablo listings.id'ye bağlandığında liste güncellenmezse Postgres
    kısıtı DELETE'i reddeder ve uç 500 verir — SQLite'ta kısıtlar varsayılan
    kapalı olduğu için testler bunu YAKALAMAZ, hata yalnızca üretimde çıkar.
    (Aynı hatanın users.id sürümü için bkz.
    tests/test_account_delete_references.py.)

    Kırıldıysa: yeni sütunu app/listings.py::purge_listing'e ekle ve kararını
    yaz — silinecek mi (konusu kalmadı) yoksa NULL'a mı çekilecek (kayıt
    kendi başına anlamlı, ör. matches).
    """
    listing_id_col = models.Listing.__table__.c.id
    bulunan = {
        f"{table.name}.{column.name}"
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if any(fk.column is listing_id_col for fk in column.foreign_keys)
    }
    assert bulunan == {"swipes.listing_id", "matches.listing_id"}


# ---------------------------------------------------------------------------
# başkasının ilanını DÜZENLEME
# ---------------------------------------------------------------------------

def test_yonetici_baskasinin_ilanini_duzenler(client):
    """Sahiplik şartı yok — sorunların çoğu tek satır düzeltmeyle çözülüyor."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description="Ara: 0532 123 45 67"
    )

    res = client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"description": "İletişim uygulama üzerinden.", "rent": 17000},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["description"] == "İletişim uygulama üzerinden."
    assert body["rent"] == 17000
    # Temiz metin işareti düşürür: yönetici hem düzeltti hem kuyruğu boşalttı.
    assert body["is_flagged"] is False
    assert body["flag_reasons"] == []

    # Değişiklik gerçekten kalıcı ve herkese görünür.
    assert client.get(f"/api/listings/{listing_id}").json()["rent"] == 17000


def test_ayni_ilani_sahibi_olmayan_normal_kullanici_duzenleyemez(client):
    """Karşılaştırma: yetki yöneticiye özel, herkese açılmadı."""
    _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ali["headers"])

    assert client.patch(
        f"/api/listings/{listing_id}",
        headers=ayse["headers"],
        json={"rent": 1},
    ).status_code == 403
    assert client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=ayse["headers"],
        json={"rent": 1},
    ).status_code == 403


def test_yonetici_duzenlemesinde_kufur_422_degil_isaretlenir(client):
    """Denetim yöneticiyi ENGELLEMEZ ama sonucu kayda yazılır.

    Aynı metin normal kullanıcı yolunda 422 alır. Yöneticiyi de reddetmek,
    düzeltmeye gelen kişiyi tam da düzeltmek istediği metin yüzünden dışarıda
    bırakırdı. Muafiyet değil: metin kaydedilir AMA işaretlenir, yani
    inceleme kuyruğunda görünür.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    # Önce sahibinin aynı metinle ne yaşadığını sabitleyelim.
    assert client.patch(
        f"/api/listings/{listing_id}",
        headers=ali["headers"],
        json={"description": BLOCKED_TEXT},
    ).status_code == 422

    res = client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"description": BLOCKED_TEXT},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["description"] == BLOCKED_TEXT
    assert body["is_flagged"] is True
    assert body["flag_reasons"], "engellenen metin gerekçesiz işaretlenmiş"
    assert body["flag_reasons_text"]

    # İşaret gerçek: kayıt inceleme kuyruğuna düştü.
    kuyruk = client.get(
        "/api/admin/flagged?kind=listing", headers=admin["headers"]
    ).json()
    assert [row["id"] for row in kuyruk] == [listing_id]


def test_yonetici_pasif_ve_kaldirilmis_ilani_da_duzenleyebilir(client):
    """Sahibin ucu pasif ilanı 404 sayar; yönetici ucu onu bulmak zorunda."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    client.delete(f"/api/listings/{listing_id}", headers=ali["headers"])

    assert client.patch(
        f"/api/listings/{listing_id}",
        headers=ali["headers"],
        json={"title": "Yeni başlık olsun"},
    ).status_code == 404

    res = client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"title": "Yeni başlık olsun"},
    )
    assert res.status_code == 200, res.text
    # Düzenleme yayın durumunu DEĞİŞTİRMEZ: sahibinin kararı yerinde.
    assert res.json()["is_active"] is False


def test_duzenleme_denetim_kaydina_onceki_metni_yazar(client):
    """Düzenleme geri alınabilir görünür ama ÖNCEKİ METİN yok olur."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"description": "Yeni açıklama.", "rent": 15000},
    )

    kayit = _actions(client, admin)[0]
    assert kayit["action"] == "listing_update"
    assert kayit["target_id"] == listing_id
    detay = json.loads(kayit["detail"])
    assert detay["fields"] == ["description", "rent"]
    assert detay["before"]["description"] == "Moda'ya 5 dakika, geniş salon."


def test_degisiklik_yoksa_denetim_kaydi_yazilmaz(client):
    """Aynı değeri tekrar göndermek kaydı şişirmemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    res = client.patch(
        f"/api/admin/listings/{listing_id}",
        headers=admin["headers"],
        json={"rent": 18000},  # zaten bu değerde
    )
    assert res.status_code == 200, res.text
    assert _actions(client, admin) == []


def test_olmayan_ilani_duzenleme_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    assert client.patch(
        "/api/admin/listings/9999",
        headers=admin["headers"],
        json={"rent": 1000},
    ).status_code == 404


# ---------------------------------------------------------------------------
# yayına alma
# ---------------------------------------------------------------------------

def test_sahibinin_kapattigi_ilan_yayina_doner(client):
    """Kapatma kullanıcı açısından tek yönlüydü; artık bir dönüş yolu var."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    client.delete(f"/api/listings/{listing_id}", headers=ali["headers"])
    assert client.get(f"/api/listings/{listing_id}").status_code == 404

    res = client.post(
        f"/api/admin/listings/{listing_id}/publish", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json() == {
        "id": listing_id,
        "is_active": True,
        "changed": True,
        "moderation_removed": False,
        "owner_suspended": False,
    }
    # Gerçekten yayında: herkese açık uçtan görünüyor.
    assert client.get(f"/api/listings/{listing_id}").status_code == 200


def test_zaten_yayindaki_ilanda_changed_false(client):
    """Uç başarılı döner ama "yayına aldım" demez."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])

    res = client.post(
        f"/api/admin/listings/{listing_id}/publish", headers=admin["headers"]
    )
    assert res.status_code == 200, res.text
    assert res.json()["changed"] is False
    assert res.json()["is_active"] is True
    # Boş yere denetim kaydı da yazılmadı.
    assert _actions(client, admin) == []


def test_yoneticinin_kaldirdigi_ilan_publish_409(client):
    """İki uç aynı alanı iki farklı kuralla yazmasın.

    moderation_removed=True olan kaydın yayın durumu active_before_removal'a
    göre geri alınır; o iş restore ucuna aittir. publish burada karar verseydi
    sahibinin kendi kapatma kararını da sessizce ezerdi.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(
        client, ali["headers"], description=FLAGGED_LISTING_TEXT
    )
    assert client.post(
        f"/api/admin/flagged/listing/{listing_id}/review",
        headers=admin["headers"],
        json={"action": "remove"},
    ).status_code == 200

    res = client.post(
        f"/api/admin/listings/{listing_id}/publish", headers=admin["headers"]
    )
    assert res.status_code == 409, res.text
    assert "restore" in res.json()["detail"]

    # Doğru yol çalışıyor ve ilan geri geliyor.
    assert client.post(
        f"/api/admin/listing/{listing_id}/restore", headers=admin["headers"]
    ).json()["is_active"] is True


def test_publish_askidaki_sahibi_bildirir(client):
    """"Yayında" ile "görünür" aynı şey değil; yanıt bunu söylüyor."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    client.delete(f"/api/listings/{listing_id}", headers=ali["headers"])
    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "İnceleme"},
    )

    body = client.post(
        f"/api/admin/listings/{listing_id}/publish", headers=admin["headers"]
    ).json()
    assert body["is_active"] is True
    assert body["owner_suspended"] is True
    # Askıdaki sahibin ilanı hâlâ hiçbir genel listede yok.
    assert client.get("/api/listings").json() == []


def test_olmayan_ilani_yayina_alma_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    assert client.post(
        "/api/admin/listings/9999/publish", headers=admin["headers"]
    ).status_code == 404


# ---------------------------------------------------------------------------
# hesabı KALICI silme
# ---------------------------------------------------------------------------

def test_yonetici_hesabi_kalici_siler(ctx):
    client, Session = ctx
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali, ayse, listing_id, match_id = _matched_pair(client)

    res = _delete_user(client, admin, ayse["id"], reason="Kullanıcı talebi")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "user"
    assert body["id"] == ayse["id"]
    assert body["deleted"] is True

    with Session() as db:
        assert db.get(models.User, ayse["id"]) is None
        # Eşleşme ve mesajlar da gitti: sohbetin yarısını bırakmanın anlamı yok.
        assert db.scalar(select(func.count()).select_from(models.Match)) == 0

    # Oturumu düştü.
    assert client.get("/api/auth/me", headers=ayse["headers"]).status_code == 401
    # Ali'nin ilanı duruyor: silinen hesap yalnızca kendi verisini götürür.
    assert client.get(f"/api/listings/{listing_id}").status_code == 200


def test_hesap_silme_denetim_kaydi_yazar(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    body = _delete_user(
        client, admin, ali["id"], reason="Tekrar tekrar açılan sahte hesap"
    ).json()

    kayit = _actions(client, admin)[0]
    assert kayit["id"] == body["action_id"]
    assert kayit["action"] == "user_delete"
    assert kayit["target_type"] == "user"
    assert kayit["target_id"] == ali["id"]
    assert kayit["reason"] == "Tekrar tekrar açılan sahte hesap"
    # "Hangi hesabı sildim" sorusunun cevabı yalnızca id ise cevap yok demektir.
    detay = json.loads(kayit["detail"])
    assert detay["email"] == "ali@uni.edu.tr"
    assert detay["name"] == "Ali"


@pytest.mark.parametrize(
    "govde",
    [None, {}, {"reason": "  "}],
    ids=["gövdesiz", "boş-gövde", "boşluk-gerekçe"],
)
def test_hesap_silme_gerekce_zorunlu(client, govde):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    kwargs = {"headers": admin["headers"]}
    if govde is not None:
        kwargs["json"] = govde
    res = client.request("DELETE", f"/api/admin/users/{ali['id']}", **kwargs)
    assert res.status_code == 422, res.text
    assert client.get("/api/auth/me", headers=ali["headers"]).status_code == 200


def test_olmayan_hesabi_silme_404(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    assert _delete_user(client, admin, 9999).status_code == 404


# ---------------------------------------------------------------------------
# korunan sınır: yönetici kendini kilitleyemez
# ---------------------------------------------------------------------------

def test_yonetici_kendini_silemez(client):
    """Son yönetici kendini silerse platformun yönetimi geri gelmez.

    Bu bir yetki kısıtı değil, kullanıcıyı kendi hatasından koruyan bir
    emniyet: kişi kendi hesabını DELETE /api/auth/me ile (şifresini girerek)
    yine silebilir — aşağıdaki son satır bunu doğruluyor.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")

    res = _delete_user(client, admin, admin["id"], reason="deneme")
    assert res.status_code == 400, res.text
    assert client.get("/api/auth/me", headers=admin["headers"]).status_code == 200
    # Denetim kaydı da yazılmadı: gerçekleşmeyen eylem kaydedilmez.
    assert _actions(client, admin) == []

    # Bilinçli ve doğrulanmış yol açık kalmalı.
    assert client.request(
        "DELETE",
        "/api/auth/me",
        headers=admin["headers"],
        json={"password": "Sifre1234"},
    ).status_code == 204


@pytest.mark.skipif(
    SECOND_ADMIN is None, reason="Kurulumda tek yönetici e-postası tanımlı"
)
def test_yonetici_baska_yoneticiyi_silemez(client):
    """Bir yönetici hesabının ele geçirilmesi tüm ekibi silmeye yetmemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    other = _make_user(client, SECOND_ADMIN, "Diğer Yönetici")

    res = _delete_user(client, admin, other["id"], reason="deneme")
    assert res.status_code == 403, res.text
    assert client.get("/api/auth/me", headers=other["headers"]).status_code == 200


# ---------------------------------------------------------------------------
# arama
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sorgu", ["ays", "AYS", "ayse@uni", "AYSE@UNI.EDU.TR", "uni.edu"]
)
def test_kullanici_aramasi_kismi_ve_harf_duyarsiz(client, sorgu):
    """?q= hem adda hem e-postada, kısmi ve harf duyarsız çalışır.

    ("uni.edu" ikisini de getirir; aşağıda yalnız Ayşe'nin bulunduğunu
    doğrulayan sorgularla birlikte "hiç filtrelemiyor" ihtimalini de eliyor.)
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayse")
    _make_user(client, "mehmet@baska.edu.tr", "Mehmet")

    bulunan = client.get(
        f"/api/admin/users?q={sorgu}", headers=admin["headers"]
    ).json()
    assert ayse["id"] in {u["id"] for u in bulunan}
    if sorgu != "uni.edu":
        assert [u["id"] for u in bulunan] == [ayse["id"]]


def test_kullanici_aramasi_epostayi_bulur_ama_dondurmez(client):
    """Aramada kullanılan alan, yanıtta dönmesini gerektirmiyor (ilke 3)."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _make_user(client, "gizli@uni.edu.tr", "Ali")

    bulunan = client.get(
        "/api/admin/users?q=gizli", headers=admin["headers"]
    ).json()
    assert len(bulunan) == 1
    assert bulunan[0]["name"] == "Ali"
    assert bulunan[0]["email"] is None


def test_arama_joker_karakteri_kacirilir(client):
    """"%" yazan arama tüm tabloyu getirmemeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    _make_user(client, "ali@uni.edu.tr", "Ali")

    assert client.get(
        "/api/admin/users?q=%25", headers=admin["headers"]
    ).json() == []


def test_kullanici_aramasi_askidakilerle_birleseblir(client):
    """q ve suspended birlikte kullanılabilir."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    _make_user(client, "alican@uni.edu.tr", "Alican")
    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Spam"},
    )

    bulunan = client.get(
        "/api/admin/users?q=ali&suspended=true", headers=admin["headers"]
    ).json()
    assert [u["id"] for u in bulunan] == [ali["id"]]
    # Askıdaki hesabın e-postası kararı doğrulamak için dönüyor.
    assert bulunan[0]["email"] == "ali@uni.edu.tr"


# ---------------------------------------------------------------------------
# tüm ilanlar listesi
# ---------------------------------------------------------------------------

def test_ilan_listesi_gizlenenleri_de_gosterir(client):
    """/api/listings'in tasarımı gereği sakladıkları burada görünmeli."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    yayinda = _make_listing(client, ali["headers"])
    kapali = _make_listing(client, ali["headers"], title="Sahibi kapattı")
    client.delete(f"/api/listings/{kapali}", headers=ali["headers"])
    kaldirilan = _make_listing(
        client,
        ali["headers"],
        title="Yönetici kaldırdı",
        description=FLAGGED_LISTING_TEXT,
    )
    client.post(
        f"/api/admin/flagged/listing/{kaldirilan}/review",
        headers=admin["headers"],
        json={"action": "remove"},
    )

    # Genel uç yalnız birini gösteriyor.
    assert [r["id"] for r in client.get("/api/listings").json()] == [yayinda]

    def ids(**params):
        res = client.get(
            "/api/admin/listings", headers=admin["headers"], params=params
        )
        assert res.status_code == 200, res.text
        return {r["id"] for r in res.json()}

    assert ids() == {yayinda, kapali, kaldirilan}
    assert ids(status="active") == {yayinda}
    assert ids(status="inactive") == {kapali}  # SAHİBİNİN kararı
    assert ids(status="removed") == {kaldirilan}  # YÖNETİCİNİN kararı


def test_ilan_aramasi_baslik_ilce_ve_sahip(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    alininki = _make_listing(client, ali["headers"], title="Moda'da stüdyo")
    aysenınki = _make_listing(
        client, ayse["headers"], title="Beşiktaş'ta oda", district="Beşiktaş"
    )

    def ids(q):
        return {
            r["id"]
            for r in client.get(
                "/api/admin/listings", headers=admin["headers"], params={"q": q}
            ).json()
        }

    assert ids("moda") == {alininki}  # başlık
    assert ids("kadıköy") == {alininki}  # ilçe
    assert ids("ali@uni") == {alininki}  # sahibin e-postası
    assert ids("Ayşe") == {aysenınki}  # sahibin adı
    assert ids("bulunamaz") == set()


def test_ilan_listesi_sahibi_askida_olani_isaretler(client):
    """Yayında görünen bir ilan aslında kimseye görünmüyor olabilir."""
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    listing_id = _make_listing(client, ali["headers"])
    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "İnceleme"},
    )

    row = client.get("/api/admin/listings", headers=admin["headers"]).json()[0]
    assert row["id"] == listing_id
    assert row["is_active"] is True
    assert row["owner_suspended"] is True


# ---------------------------------------------------------------------------
# denetim kaydı listesi
# ---------------------------------------------------------------------------

def test_denetim_kaydi_en_yeni_once_ve_suzulebilir(client):
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")
    ayse = _make_user(client, "ayse@uni.edu.tr", "Ayşe")
    listing_id = _make_listing(client, ali["headers"])

    _delete_listing(client, admin, listing_id, reason="İlan sebebi")
    _delete_user(client, admin, ayse["id"], reason="Hesap sebebi")

    hepsi = _actions(client, admin)
    assert [k["action"] for k in hepsi] == ["user_delete", "listing_delete"]

    assert [k["reason"] for k in _actions(client, admin, action="listing_delete")] == [
        "İlan sebebi"
    ]
    assert [k["reason"] for k in _actions(client, admin, target_type="user")] == [
        "Hesap sebebi"
    ]
    # Sayfalama
    assert len(_actions(client, admin, limit=1)) == 1
    assert _actions(client, admin, limit=1, offset=1)[0]["action"] == "listing_delete"


def test_askiya_alma_denetim_kaydina_yazilmaz(client):
    """Geri alınabilir eylemler izini KENDİ sütunlarında bırakır.

    Aynı olayı iki yerde tutmak, ikisinin çelişmesi demektir: askı kaldırılıp
    yeniden konduğunda AdminAction'daki kopya yürürlükteki durumu yanlış
    anlatırdı. Askının izi users.suspended_by/suspended_at'tedir.
    """
    admin = _make_user(client, ADMIN_EMAIL, "Yönetici")
    ali = _make_user(client, "ali@uni.edu.tr", "Ali")

    client.post(
        f"/api/admin/users/{ali['id']}/suspend",
        headers=admin["headers"],
        json={"reason": "Spam"},
    )
    client.post(
        f"/api/admin/users/{ali['id']}/unsuspend", headers=admin["headers"]
    )

    assert _actions(client, admin) == []
    askili = client.get(
        f"/api/admin/users?q=ali", headers=admin["headers"]
    ).json()[0]
    assert askili["unsuspended_by"] == admin["id"]
    assert askili["last_suspension_reason"] == "Spam"
