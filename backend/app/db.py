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


def get_db():
    """İstek başına bir oturum açan FastAPI bağımlılığı."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
