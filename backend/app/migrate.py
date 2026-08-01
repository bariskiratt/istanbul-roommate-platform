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
    ),
    "messages": (_Column("is_flagged", "BOOLEAN", default=False),),
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
    return applied
