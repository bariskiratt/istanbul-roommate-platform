"""Veritabanı bağlantısı ve oturum yönetimi.

Yerelde tek dosyalık SQLite yeterli. Yayında DATABASE_URL ortam değişkeni
verilirse (ör. Render/Railway Postgres'i: postgresql://...) o kullanılır.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DB_PATH

_url = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
# SQLAlchemy 2 + psycopg3 sürücüsü "postgresql+psycopg://" ister;
# sağlayıcılar genelde "postgres(ql)://" verir, burada düzeltiyoruz.
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+psycopg://", 1)
elif _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    _url,
    # check_same_thread yalnız SQLite için: FastAPI istekleri farklı
    # thread'lerden gelebilir; oturumlar istek başına açılıp kapanıyor.
    connect_args=(
        {"check_same_thread": False} if _url.startswith("sqlite") else {}
    ),
    pool_pre_ping=not _url.startswith("sqlite"),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Tabloları (yoksa) oluşturur. Sunucu açılışında çağrılır."""
    from app import models  # noqa: F401 — tabloların Base'e kaydolması için

    Base.metadata.create_all(engine)
    _migrate(engine)


def _migrate(target) -> None:
    """create_all mevcut tabloya kolon eklemez; küçük şema farklarını burada
    kapatıyoruz. (Alembic bu proje ölçeği için fazla.)"""
    from sqlalchemy import inspect, text

    columns = {c["name"] for c in inspect(target).get_columns("listings")}
    if "owner_id" not in columns:
        with target.begin() as conn:
            conn.execute(
                text("ALTER TABLE listings ADD COLUMN owner_id INTEGER "
                     "REFERENCES users(id)")
            )


def get_db():
    """İstek başına bir oturum açan FastAPI bağımlılığı."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
