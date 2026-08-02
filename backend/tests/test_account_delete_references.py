"""HESAP SİLME, users.id'ye BAĞLI HER YABANCI ANAHTARDA ÇALIŞMAK ZORUNDA.

BU DOSYA NE İŞE YARIYOR
-----------------------
Hesap silen İKİ uç var ve ikisi de aynı temizliği yapmak zorunda:
    DELETE /api/auth/me          kişinin kendisi (şifre doğrulamasıyla)
    DELETE /api/admin/users/{id} yönetici (gerekçe zorunlu)
Silinen kullanıcıya işaret eden her satır ya silinmeli ya da o alan NULL'a
çekilmeli. Bir tanesi bile atlanırsa Postgres'in yabancı anahtar kısıtı
silmeyi reddeder, hata yakalanmadığı için istek 500 verir ve HESAP SİLİNEMEZ.

Aşağıdaki testler her yabancı anahtarı İKİ UÇ İÇİN DE ayrı ayrı koşar. İkisi
de app.auth.purge_user'ı çağırdığı için normalde aynı sonucu vermeleri
gerekir; testin ikisini birden koşmasının sebebi tam olarak budur — biri
gün gelip kendi silme listesini yazmaya kalkarsa burada yakalanır.

Bu hata bu projede İKİ KEZ yaşandı:
  1. reports.reporter_id eklendiğinde (düzeltildi, auth.py'de yorumu duruyor),
  2. sonra users.suspended_by, listings.reviewed_by, messages.reviewed_by ve
     reports.resolved_by eklendiğinde AYNEN tekrarladı — yönetici tek bir
     moderasyon eylemi yapınca kendi hesabını silemez hâle geliyordu.

Sebep, korumanın elle yazılmış olmasıydı: yeni sütun ekleyen kişi
auth.py'yi güncellemeyi unutuyor, hiçbir test de bunu fark etmiyordu.

Bu yüzden aşağıdaki test SABİT BİR LİSTE KULLANMAZ. users.id'ye işaret eden
yabancı anahtarları SQLAlchemy metadata'sından, yani models.py'nin
kendisinden okur ve her biri için ayrı ayrı koşar:

  - o sütunu silinecek kullanıcıya bağlayan gerçek bir satır üretir
    (satırın diğer zorunlu alanları ve bağlı olduğu tablolar da üretilir),
  - hesabı API'den sildirir ve 204 bekler,
  - silmeden sonra HİÇBİR tabloda o kullanıcıya işaret eden satır kalmadığını
    doğrular.

Sonuç: models.py'ye users.id'ye bakan yeni bir sütun eklendiği anda bu test
kendiliğinden o sütun için de koşar. auth.py güncellenmemişse test KIRILIR.
Yani koruma artık geliştiricinin hafızasına değil şemaya bağlı.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    JSON,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app

EMAIL = "silinecek@uni.edu.tr"
PASSWORD = "Sifre1234"
# config.ADMIN_EMAILS ortam değişkeninden okunur; kurulum farkı testi kırmasın
# diye listeden birini alıp yönetici hesabını onunla kuruyoruz.
ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]

_USER_ID = models.User.__table__.c.id
# Tablo adı -> ORM sınıfı. Genel satır üreticisi tabloyu görüp modeli bulur.
_MODEL_BY_TABLE = {
    mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
}


def _user_fk_columns() -> list:
    """users.id'ye işaret eden TÜM sütunlar (nullable olsun olmasın)."""
    return [
        column
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if any(fk.column is _USER_ID for fk in column.foreign_keys)
    ]


# Toplama anında okunur; models.py değişince parametre listesi de değişir.
_FK_COLUMNS = _user_fk_columns()
_FK_IDS = [f"{c.table.name}.{c.name}" for c in _FK_COLUMNS]


class _RowMaker:
    """Bir tabloya, zorunlu alanları doldurulmuş geçerli bir satır ekler.

    Elle kurulum yazmamak için gerekiyor: test hangi tabloya satır atacağını
    şemadan öğrendiği için o tablonun alanlarını da şemadan doldurmalı.
    Bağlı olduğu tablolar (ör. messages -> matches -> users) özyinelemeli
    olarak üretilir.
    """

    def __init__(self, db):
        self.db = db
        self._n = 0

    def _uniq(self) -> int:
        self._n += 1
        return self._n

    def _value(self, column):
        if column.foreign_keys:
            target = next(iter(column.foreign_keys)).column
            return self.create(target.table).id
        if isinstance(column.type, Boolean):
            return False
        if isinstance(column.type, Integer):
            return 1
        if isinstance(column.type, JSON):
            return []
        if isinstance(column.type, DateTime):
            return datetime(2024, 1, 1)
        # Kalan her şey metin. Sayaç, unique kısıtlarını (users.email,
        # auth_tokens.token_hash) tek tek ele almaktan kurtarıyor.
        return f"dolgu{self._uniq()}"

    def create(self, table, **overrides):
        model = _MODEL_BY_TABLE[table.name]
        kwargs = dict(overrides)
        for column in table.columns:
            if column.name in kwargs or column.primary_key:
                continue
            # Nullable ya da varsayılanı olan alanlar boş bırakılabilir.
            if column.nullable or column.default is not None:
                continue
            kwargs[column.name] = self._value(column)
        row = model(**kwargs)
        self.db.add(row)
        self.db.flush()
        return row


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


def _register(client, email: str = EMAIL) -> tuple[dict, int]:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    )
    data = client.post(
        "/api/auth/verify-otp",
        json={"email": email, "code": res.json()["dev_code"]},
    ).json()
    return {"Authorization": f"Bearer {data['token']}"}, data["user"]["id"]


def _delete_kendi(client, headers, uid):
    """DELETE /api/auth/me — kişinin kendisi, şifreyle. Başarı: 204."""
    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": PASSWORD}
    )
    return res, 204


def _delete_yonetici(client, headers, uid):
    """DELETE /api/admin/users/{id} — yönetici, gerekçeyle. Başarı: 200."""
    admin_headers, _ = _register(client, ADMIN_EMAIL)
    res = client.request(
        "DELETE",
        f"/api/admin/users/{uid}",
        headers=admin_headers,
        json={"reason": "Test: kalıcı silme"},
    )
    return res, 200


# Her yabancı anahtar bu iki yolun İKİSİ İÇİN DE denenir.
_DELETE_PATHS = {"kendi": _delete_kendi, "yonetici": _delete_yonetici}


def _referencing_rows(db, user_id: int) -> dict[str, int]:
    """Kullanıcıya hâlâ işaret eden satır sayıları (sütun adına göre)."""
    counts = {}
    for column in _user_fk_columns():
        found = db.scalar(
            select(func.count()).select_from(column.table).where(column == user_id)
        )
        if found:
            counts[f"{column.table.name}.{column.name}"] = found
    return counts


def test_sema_gercekten_yabanci_anahtar_tasiyor():
    """Parametre listesi boşalırsa aşağıdaki test sessizce hiç koşmaz."""
    assert len(_FK_COLUMNS) >= 8, _FK_IDS


@pytest.mark.parametrize("yol", _DELETE_PATHS)
@pytest.mark.parametrize("column", _FK_COLUMNS, ids=_FK_IDS)
def test_hesap_silme_her_yabanci_anahtari_temizler(ctx, column, yol):
    """users.id'ye bakan HER sütun için: hesap İKİ YOLDAN DA silinebilmeli.

    Bu test kırıldıysa yapılacak şey, app/auth.py'deki purge_user'a o sütunu
    eklemektir (iki uç da orayı çağırır). Sütun nullable ise oradaki genel
    süpürme (_nullable_user_fk_columns) zaten hallediyor olmalı; NOT NULL ise
    ilgili satırların açıkça silinmesi gerekir.
    """
    client, Session = ctx
    headers, uid = _register(client)

    with Session() as db:
        maker = _RowMaker(db)
        maker.create(column.table, **{column.name: uid})
        db.commit()
        assert _referencing_rows(db, uid), "kurulum satırı gerçekten bağlanmadı"

    res, beklenen = _DELETE_PATHS[yol](client, headers, uid)
    assert res.status_code == beklenen, res.text

    with Session() as db:
        assert db.get(models.User, uid) is None
        assert _referencing_rows(db, uid) == {}


@pytest.mark.parametrize("yol", _DELETE_PATHS)
def test_denetim_kaydinin_aktoru_silinince_kayit_kaybolmaz(ctx, yol):
    """Silinen kullanıcı bir denetim kaydının AKTÖRÜ ise kayıt DURUR.

    admin_actions, geri alınamaz eylemlerin (kalıcı silme) tek izidir. Aktörü
    silinince kaydın da silinmesi, izini yok etmenin en kolay yolunu "kendi
    hesabını sil" yapardı. Doğru davranış: actor_id NULL'a düşer, satır kalır.
    """
    client, Session = ctx
    headers, uid = _register(client)

    with Session() as db:
        db.add(
            models.AdminAction(
                actor_id=uid,
                action="listing_delete",
                target_type="listing",
                target_id=4242,
                reason="Hukuki kaldırma talebi",
            )
        )
        db.commit()

    res, beklenen = _DELETE_PATHS[yol](client, headers, uid)
    assert res.status_code == beklenen, res.text

    with Session() as db:
        kayit = db.scalar(
            select(models.AdminAction).where(models.AdminAction.target_id == 4242)
        )
        assert kayit is not None, "denetim kaydı aktörüyle birlikte silinmiş"
        assert kayit.actor_id is None
        # Eylemin KENDİSİ ve gerekçesi duruyor; kaybolan yalnızca imza.
        assert kayit.action == "listing_delete"
        assert kayit.reason == "Hukuki kaldırma talebi"


def test_yonetici_moderasyon_yaptiktan_sonra_hesabini_silebilir(ctx):
    """Bildirilen hatanın birebir senaryosu — okunabilir hâli.

    Yönetici bir kullanıcıyı askıya alır, ilan ve mesaj inceler, rapor
    kapatır; sonra kendi hesabını siler. Denetim izi sütunları
    temizlenmezse bu istek IntegrityError ile 500 verirdi.
    """
    client, Session = ctx
    headers, uid = _register(client)

    with Session() as db:
        maker = _RowMaker(db)
        # Askıya alınan kullanıcı, incelenen ilan/mesaj, kapatılan rapor:
        # dördünün de "kim yaptı" alanı silinecek hesabı gösteriyor.
        maker.create(models.User.__table__, suspended_by=uid, unsuspended_by=uid)
        maker.create(models.Listing.__table__, reviewed_by=uid)
        maker.create(models.Message.__table__, reviewed_by=uid)
        maker.create(models.Report.__table__, resolved_by=uid)
        db.commit()

    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": PASSWORD}
    )
    assert res.status_code == 204, res.text

    with Session() as db:
        # Kararların KENDİSİ duruyor, yalnızca aktörü kayboldu: hesabını
        # silme hakkı, moderasyon geçmişindeki imzadan önce gelir.
        assert db.scalar(select(func.count()).select_from(models.Listing)) == 1
        assert db.scalar(select(func.count()).select_from(models.Report)) == 1
        assert _referencing_rows(db, uid) == {}
