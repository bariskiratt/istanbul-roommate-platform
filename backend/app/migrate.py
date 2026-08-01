"""Şema migrasyonu — mevcut tablolara eksik sütunları ekler.

`Base.metadata.create_all` yalnızca OLMAYAN tabloyu oluşturur; var olan bir
tabloya sütun eklemez. Alembic bu proje ölçeği için fazla olduğundan
sütun farkları burada elle kapatılıyor.

Üretimde canlı Postgres var; bu yüzden:
- hiçbir sütun/tablo SİLİNMEZ, sadece eklenir,
- tekrar tekrar çalıştırılabilir (idempotent),
- sütun listesi Postgres'te information_schema.columns, SQLite'ta
  PRAGMA table_info ile okunur.

Uygulama açılışında bir kez çağrılır (main.py lifespan).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class _Column:
    """Eklenecek sütunun tanımı."""

    name: str
    sql_type: str
    # None: varsayılan yok (NULL = belirtilmemiş).
    # False/True: ALTER TABLE ile eklenirken mevcut satırlara da yazılır.
    default: bool | None = None
    references: str | None = None


# Tablo -> eklenecek sütunlar. Yeni bir alan eklerken hem models.py'ye hem
# buraya yazılmalı.
_SCHEMA: dict[str, tuple[_Column, ...]] = {
    "users": (
        # Askıya alma — eski satırlar aktif sayılır.
        _Column("is_suspended", "BOOLEAN", default=False),
        _Column("suspended_at", "TIMESTAMP"),
        _Column("suspended_reason", "VARCHAR(500)"),
        _Column("suspended_by", "INTEGER", references="users(id)"),
        # Askının kaldırılmasının izi — eski satırlarda NULL ("hiç
        # askıya alınmamış" ile "askısı kaldırılmış" ayrımı korunur).
        _Column("unsuspended_at", "TIMESTAMP"),
        _Column("unsuspended_by", "INTEGER", references="users(id)"),
        _Column("last_suspension_reason", "VARCHAR(500)"),
    ),
    "listings": (
        # Auth öncesi dönemden kalan tablolarda olmayabilir.
        _Column("owner_id", "INTEGER", references="users(id)"),
        # Ev özellikleri — hepsi nullable (NULL = belirtilmemiş).
        _Column("furnished", "BOOLEAN"),
        _Column("elevator", "BOOLEAN"),
        _Column("parking", "BOOLEAN"),
        _Column("internet_included", "BOOLEAN"),
        _Column("heating_included", "BOOLEAN"),
        _Column("balcony", "BOOLEAN"),
        _Column("natural_gas", "BOOLEAN"),
        # Denetim işareti — eski satırlar temiz sayılır.
        _Column("is_flagged", "BOOLEAN", default=False),
        # Denetim gerekçeleri ve yönetici incelemesi — eski satırlarda NULL.
        _Column("flag_reasons", "TEXT"),
        _Column("reviewed_by", "INTEGER", references="users(id)"),
        _Column("reviewed_at", "TIMESTAMP"),
        _Column("review_note", "VARCHAR(500)"),
        # Yönetici kaldırması — eski satırlar "yönetici kaldırmadı" sayılır
        # (sahibin kendi kapattığı ilanlar da böylece ayrık kalır).
        _Column("moderation_removed", "BOOLEAN", default=False),
        # Kaldırma anındaki yayın durumu; geri alma buraya döner.
        # VARSAYILAN YOK (NULL): bu sütun gelmeden önce kaldırılmış kayıtlarda
        # önceki durum gerçekten bilinmiyor. False yazsaydık o ilanlar geri
        # alındığında sessizce kapalı kalırdı.
        _Column("active_before_removal", "BOOLEAN"),
    ),
    "messages": (
        _Column("is_flagged", "BOOLEAN", default=False),
        _Column("flag_reasons", "TEXT"),
        _Column("reviewed_by", "INTEGER", references="users(id)"),
        _Column("reviewed_at", "TIMESTAMP"),
        _Column("review_note", "VARCHAR(500)"),
        # Yönetici kaldırması ve kaldırılan metnin saklandığı yer.
        # DİKKAT: bu sütunlar gelmeden önce kaldırılmış mesajların metni
        # üzerine yazıldığı için geri getirilemez; yalnızca bundan sonraki
        # kaldırmalar geri alınabilir.
        _Column("moderation_removed", "BOOLEAN", default=False),
        _Column("original_content", "TEXT"),
    ),
    "reports": (
        # Raporu kimin, ne zaman kapattığı — eski satırlarda NULL.
        _Column("resolved_by", "INTEGER", references="users(id)"),
        _Column("resolved_at", "TIMESTAMP"),
    ),
}


def _existing_columns(conn, table: str, dialect: str) -> set[str]:
    """Tablodaki sütun adları. Tablo yoksa boş küme döner."""
    if dialect == "postgresql":
        # table_schema filtresi şart: aynı adlı tablo başka bir şemada da
        # varsa (ör. eski bir kopya) sütunlar birleşir ve gerçekten eksik
        # olan sütun "var" sanılıp atlanır.
        rows = conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = :t AND table_schema = current_schema()"
            ),
            {"t": table},
        )
        return {row[0] for row in rows}
    if dialect == "sqlite":
        rows = conn.execute(text(f'PRAGMA table_info("{table}")'))
        return {row[1] for row in rows}
    # Bilinmeyen sürücü: SQLAlchemy'nin genel denetleyicisine düş.
    return {col["name"] for col in inspect(conn).get_columns(table)}


def _default_literal(default: bool, dialect: str) -> str:
    if dialect == "postgresql":
        return "TRUE" if default else "FALSE"
    # SQLite (ve diğerleri) boolean'ı tam sayı olarak saklar.
    return "1" if default else "0"


def _add_column_sql(table: str, column: _Column, dialect: str) -> str:
    # Postgres'te IF NOT EXISTS: iki süreç (rolling deploy, birden çok worker)
    # aynı anda açılırsa ikincisi "column already exists" ile patlamasın —
    # yoksa uygulama hiç ayağa kalkmaz. SQLite bu sözdizimini desteklemez,
    # orada sütun listesi kontrolü tek başına yeterli.
    exists_guard = " IF NOT EXISTS" if dialect == "postgresql" else ""
    parts = [
        f'ALTER TABLE "{table}" ADD COLUMN{exists_guard} '
        f"{column.name} {column.sql_type}"
    ]
    if column.default is not None:
        parts.append(f"DEFAULT {_default_literal(column.default, dialect)}")
    if column.references:
        parts.append(f"REFERENCES {column.references}")
    return " ".join(parts)


def run_migrations(engine: Engine | None = None) -> list[str]:
    """Eksik sütunları ekler; eklenenlerin "tablo.sutun" listesini döner."""
    if engine is None:
        from app.db import engine as default_engine

        engine = default_engine

    dialect = engine.dialect.name
    inspector = inspect(engine)
    applied: list[str] = []

    for table, columns in _SCHEMA.items():
        if not inspector.has_table(table):
            # Tablo henüz yok; create_all onu şemanın son hâliyle oluşturur.
            continue
        with engine.begin() as conn:
            existing = _existing_columns(conn, table, dialect)
            for column in columns:
                if column.name in existing:
                    continue
                conn.execute(text(_add_column_sql(table, column, dialect)))
                applied.append(f"{table}.{column.name}")

    if applied:
        print(f"🛠  Şema güncellendi: {', '.join(applied)}", flush=True)

    _warn_on_drift(engine)
    return applied


def _warn_on_drift(engine: Engine) -> None:
    """Modelde olup veritabanında olmayan sütunları açılışta yüksek sesle bildirir.

    _SCHEMA elle tutulan bir listedir: modele yeni bir sütun eklenip buraya
    yazılmazsa yerelde (create_all ile sıfırdan doğan şema) her şey çalışır,
    ama üretimdeki eski tabloda sütun eksik kalır ve ilk istekte patlar.
    Bu kontrol o sessiz hatayı açılışta görünür bir uyarıya çevirir.
    """
    from app.db import Base

    inspector = inspect(engine)
    missing: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if not inspector.has_table(table_name):
            continue  # create_all bu tabloyu son hâliyle oluşturacak
        existing = {c["name"] for c in inspector.get_columns(table_name)}
        missing += [
            f"{table_name}.{c.name}" for c in table.columns if c.name not in existing
        ]

    if missing:
        print(
            "⚠️  ŞEMA UYUŞMAZLIĞI — bu sütunlar modelde var, veritabanında yok: "
            f"{', '.join(sorted(missing))}. app/migrate.py içindeki _SCHEMA "
            "listesine eklenmeleri gerekiyor; aksi halde bu sütunlara dokunan "
            "her istek hata verecek.",
            flush=True,
        )
