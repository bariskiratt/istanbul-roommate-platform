"""Şema migrasyonu — app/migrate.py.

Üretimde canlı bir Postgres var ve şema farkları Alembic yerine burada elle
kapatılıyor. İki şey kırılırsa üretim açılışta ya da ilk istekte patlar:

1. models.py'ye eklenen bir sütun _SCHEMA'ya YAZILMAZSA canlı veritabanında
   sütun eksik kalır; o sütuna dokunan uç çalışma anında hata verir.
2. run_migrations idempotent olmazsa her yeniden başlatma ALTER hatası verir.

Testler, gerçekten dağıtılmış ESKİ bir şemanın anlık görüntüsü üzerinde koşar.
"""

import sqlite3

import pytest
from sqlalchemy import create_engine, text

from app import models
from app.db import Base
from app.migrate import _SCHEMA, run_migrations

# Dağıtılmış eski şemanın DONDURULMUŞ anlık görüntüsü.
#
# BU TANIMLARI GÜNCELLEME. Amaçları bugünün şemasını tekrarlamak değil,
# "sahadaki en eski veritabanı" ile bugünkü models.py arasındaki farkı
# ölçmek. Buraya yeni sütun eklenirse test kendi kendini doğrular hâle gelir
# ve _SCHEMA'da unutulan sütunu artık yakalayamaz.
_FROZEN_DDL = (
    """
    CREATE TABLE users (
        id INTEGER NOT NULL PRIMARY KEY,
        email VARCHAR(254) NOT NULL,
        password_hash VARCHAR(200),
        verified BOOLEAN NOT NULL,
        name VARCHAR(80) NOT NULL,
        gender VARCHAR(30),
        birth_year INTEGER,
        university VARCHAR(80),
        department VARCHAR(80),
        year INTEGER,
        budget_min INTEGER,
        budget_max INTEGER,
        smoking BOOLEAN,
        pets BOOLEAN,
        alcohol BOOLEAN,
        sleep_schedule VARCHAR(10),
        preferred_districts JSON NOT NULL,
        bio TEXT NOT NULL,
        photos JSON NOT NULL,
        otp_hash VARCHAR(64),
        otp_expires DATETIME,
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE listings (
        id INTEGER NOT NULL PRIMARY KEY,
        owner_id INTEGER REFERENCES users (id),
        type VARCHAR(20) NOT NULL,
        title VARCHAR(120) NOT NULL,
        description TEXT NOT NULL,
        district VARCHAR(40) NOT NULL,
        photos JSON NOT NULL,
        rent INTEGER,
        room_count VARCHAR(10),
        smoking_allowed BOOLEAN,
        pets_allowed BOOLEAN,
        budget_min INTEGER,
        budget_max INTEGER,
        is_active BOOLEAN NOT NULL,
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE matches (
        id INTEGER NOT NULL PRIMARY KEY,
        user_a_id INTEGER NOT NULL REFERENCES users (id),
        user_b_id INTEGER NOT NULL REFERENCES users (id),
        listing_id INTEGER REFERENCES listings (id),
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE messages (
        id INTEGER NOT NULL PRIMARY KEY,
        match_id INTEGER NOT NULL REFERENCES matches (id),
        sender_id INTEGER NOT NULL REFERENCES users (id),
        content TEXT NOT NULL,
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE reports (
        id INTEGER NOT NULL PRIMARY KEY,
        reporter_id INTEGER NOT NULL REFERENCES users (id),
        target_type VARCHAR(20) NOT NULL,
        target_id INTEGER NOT NULL,
        reason VARCHAR(30) NOT NULL,
        note VARCHAR(500),
        created_at DATETIME NOT NULL,
        resolved BOOLEAN NOT NULL,
        resolution_note VARCHAR(500)
    )
    """,
)

_SEED = (
    "INSERT INTO users (id, email, verified, name, preferred_districts, bio,"
    " photos, created_at) VALUES"
    " (1, 'eski@ornek.com', 1, 'Eski', '[]', '', '[]', '2024-01-01 00:00:00')",
    "INSERT INTO listings (id, owner_id, type, title, description, district,"
    " photos, rent, room_count, is_active, created_at) VALUES"
    " (1, 1, 'ev_ilani', 'Eski ilan', 'Eski açıklama', 'Kadıköy', '[]',"
    " 5000, '2+1', 1, '2024-01-01 00:00:00')",
    "INSERT INTO matches (id, user_a_id, user_b_id, listing_id, created_at)"
    " VALUES (1, 1, 1, 1, '2024-01-01 00:00:00')",
    "INSERT INTO messages (id, match_id, sender_id, content, created_at) VALUES"
    " (1, 1, 1, 'eski düz metin mesaj', '2024-01-01 00:00:00')",
    "INSERT INTO reports (id, reporter_id, target_type, target_id, reason,"
    " created_at, resolved) VALUES"
    " (1, 1, 'listing', 1, 'spam', '2024-01-01 00:00:00', 0)",
)


def _columns(path: str, table: str) -> list[str]:
    con = sqlite3.connect(path)
    try:
        return [row[1] for row in con.execute(f'PRAGMA table_info("{table}")')]
    finally:
        con.close()


def _row(path: str, sql: str) -> dict:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        return dict(con.execute(sql).fetchone())
    finally:
        con.close()


@pytest.fixture()
def legacy_db(tmp_path):
    """Eski şemalı, içinde gerçek veri olan bir veritabanı."""
    path = str(tmp_path / "legacy.db")
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        for ddl in _FROZEN_DDL:
            conn.execute(text(ddl))
        for sql in _SEED:
            conn.execute(text(sql))
    return path, engine


def _expected_additions(path: str) -> list[str]:
    """Eski şemada gerçekten eksik olan _SCHEMA sütunları."""
    return sorted(
        f"{table}.{col.name}"
        for table, cols in _SCHEMA.items()
        for col in cols
        if col.name not in _columns(path, table)
    )


def test_schema_listesindeki_her_sutun_modelde_de_var():
    """_SCHEMA'da models.py'de karşılığı olmayan (yazım hatası ya da sonradan
    kaldırılmış) bir sütun kalmamalı; migrasyon üretime ölü sütun eklerdi."""
    for table, columns in _SCHEMA.items():
        declared = {c.name for c in models.Base.metadata.tables[table].columns}
        unknown = [c.name for c in columns if c.name not in declared]
        assert unknown == [], f"{table}: models.py'de yok -> {unknown}"


def test_eksik_sutunlar_eklenir_ve_eski_veri_durur(legacy_db):
    path, engine = legacy_db
    expected = _expected_additions(path)
    assert expected, "donmuş anlık görüntü zaten güncel — test anlamını yitirmiş"

    applied = run_migrations(engine)
    assert sorted(applied) == expected

    for table, columns in _SCHEMA.items():
        now = _columns(path, table)
        assert [c.name for c in columns if c.name not in now] == []

    # Var olan satırlar korunur; varsayılanı olan boolean'lar mevcut satırlara
    # da yazılır (eski kayıt "askıda" ya da "işaretli" görünmemeli).
    user = _row(path, "SELECT * FROM users WHERE id=1")
    listing = _row(path, "SELECT * FROM listings WHERE id=1")
    message = _row(path, "SELECT * FROM messages WHERE id=1")

    assert user["email"] == "eski@ornek.com"
    assert listing["title"] == "Eski ilan"
    assert message["content"] == "eski düz metin mesaj"
    assert user["is_suspended"] == 0
    assert listing["is_flagged"] == 0
    assert listing["moderation_removed"] == 0
    assert message["moderation_removed"] == 0
    # Varsayılanı olmayanlar NULL kalır ("belirtilmemiş").
    assert listing["furnished"] is None
    assert message["original_content"] is None
    # Kaldırmadan önceki yayın durumu eski kayıtlarda BİLİNMİYOR; False
    # yazsaydık geri alma o ilanları sessizce kapalı bırakırdı.
    assert listing["active_before_removal"] is None


def test_ikinci_calistirma_bos_doner(legacy_db):
    """Idempotency: her açılışta çalışır, ikinci kez hiçbir şey eklemez."""
    _, engine = legacy_db
    assert run_migrations(engine) != []
    assert run_migrations(engine) == []
    assert run_migrations(engine) == []


def test_olmayan_tablo_atlanir_create_all_dogurur(tmp_path):
    """Tablo hiç yoksa migrasyon patlamaz; create_all onu son hâliyle kurar."""
    path = str(tmp_path / "bos.db")
    engine = create_engine(f"sqlite:///{path}")
    assert run_migrations(engine) == []  # hiç tablo yok

    models.Base.metadata.create_all(engine)
    # create_all güncel şemayı kurar; migrasyonun ekleyeceği bir şey kalmaz.
    assert run_migrations(engine) == []
    for table, columns in _SCHEMA.items():
        now = _columns(path, table)
        assert [c.name for c in columns if c.name not in now] == []


def test_migre_edilen_eski_db_modelin_tum_sutunlarini_tasir(legacy_db):
    """_SCHEMA EKSİKSİZ Mİ.

    Donmuş eski şema migre edildikten sonra models.py'nin tanımladığı her
    sütun orada bulunmalı. models.py'ye sütun eklenip _SCHEMA'ya yazılmazsa
    bu test kırılır — üretimdeki eksik sütun hatası testte yakalanır.
    """
    path, engine = legacy_db
    run_migrations(engine)

    missing = {}
    for table in _SCHEMA:
        declared = [c.name for c in models.Base.metadata.tables[table].columns]
        absent = [c for c in declared if c not in _columns(path, table)]
        if absent:
            missing[table] = absent
    assert missing == {}, f"_SCHEMA'ya yazılmamış sütunlar: {missing}"


# ---- şema sürüklenmesi uyarısı ----
# _SCHEMA elle tutulan bir liste: modele sütun eklenip buraya yazılmazsa yerelde
# (create_all ile doğan şema) sorun görünmez, üretimdeki eski tabloda sütun eksik
# kalır ve ilk istekte patlar. Aşağıdaki iki test o sessiz hatanın açılışta
# görünür bir uyarıya döndüğünü doğrular.


def test_saglikli_semada_suruklenme_uyarisi_cikmaz(tmp_path, capsys):
    engine = create_engine(f"sqlite:///{tmp_path/'ok.db'}")
    Base.metadata.create_all(engine)

    run_migrations(engine)

    assert "ŞEMA UYUŞMAZLIĞI" not in capsys.readouterr().out


def test_modelde_olup_veritabaninda_olmayan_sutun_uyari_verir(tmp_path, capsys):
    engine = create_engine(f"sqlite:///{tmp_path/'drift.db'}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users DROP COLUMN bio"))

    run_migrations(engine)

    out = capsys.readouterr().out
    assert "ŞEMA UYUŞMAZLIĞI" in out
    assert "users.bio" in out
