"""SQLite bağlantısı ve oturum yönetimi.

Tek dosyalık SQLite yeterli: tek süreç, düşük yazma hacmi. İleride Postgres'e
geçiş gerekirse yalnızca buradaki engine değişir.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DB_PATH

# check_same_thread=False: FastAPI istekleri farklı thread'lerden gelebilir;
# oturumlar istek başına açılıp kapandığı için paylaşım riski yok.
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
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
