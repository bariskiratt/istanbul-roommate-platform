"""Veritabanı bağlantısı ve oturum yönetimi.

Yerelde tek dosyalık SQLite yeterli. Yayında DATABASE_URL ortam değişkeni
verilirse (ör. Render/Railway Postgres'i: postgresql://...) o kullanılır.
"""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DB_PATH


@event.listens_for(Engine, "connect")
def _sqlite_enable_foreign_keys(dbapi_connection, connection_record):
    """Her SQLite bağlantısında yabancı anahtar kısıtlarını açar.

    SQLite'ta FK zorlaması VARSAYILAN OLARAK KAPALIDIR ve bağlantı başına
    ayarlanır; üretimdeki Postgres ise her zaman zorlar. Kapalı bırakılırsa
    iki ortam sessizce ayrışır: silme sırası yanlış olan bir akış (ör. rapor
    göndermiş kullanıcının hesabını silmek) yerelde çalışır, üretimde
    IntegrityError verir.

    Dinleyici tek bir motora değil Engine sınıfına bağlanır; böylece
    uygulamanın motoru da testlerin kendi kurduğu motorlar da aynı kuralla
    çalışır ve "yerelde geçti" ile "üretimde patladı" arası fark kapanır.
    Postgres/MySQL bağlantılarında koşulsuz atlanır.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

_url = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
# SQLAlchemy 2 + psycopg3 sürücüsü "postgresql+psycopg://" ister;
# sağlayıcılar genelde "postgres(ql)://" verir, burada düzeltiyoruz.
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql+psycopg://", 1)
elif _url.startswith("postgresql://"):
    _url = _url.replace("postgresql://", "postgresql+psycopg://", 1)

def build_engine(url: str):
    """Verilen URL için motoru proje ayarlarıyla kurar.

    Ayrı bir fonksiyon olmasının sebebi test edilebilirlik: aşağıdaki modül
    seviyesindeki `engine` import anında kuruluyor, dolayısıyla ayarlarının
    doğruluğu ancak "engine.<özellik> doğru mu" diye bakarak sınanabilirdi.
    Bu fonksiyonla test kendi motorunu AYNI ayarlarla kurup davranışı
    (ör. parametre gizleme) gerçekten deneyebiliyor.
    """
    return create_engine(
        url,
        # check_same_thread yalnız SQLite için: FastAPI istekleri farklı
        # thread'lerden gelebilir; oturumlar istek başına açılıp kapanıyor.
        connect_args=(
            {"check_same_thread": False} if url.startswith("sqlite") else {}
        ),
        pool_pre_ping=not url.startswith("sqlite"),
        # SQL HATA MESAJLARINDA PARAMETRELERİ GİZLE.
        #
        # Varsayılan davranışta SQLAlchemy, patlayan sorgunun bağlı
        # parametrelerini istisna metnine ekler. Bu tabloda ne olduğu
        # düşünülünce ciddi bir sızıntıdır: users satırına yapılan hatalı bir
        # INSERT/UPDATE, password_hash ve otp_hash değerlerini DÜZ METİN
        # olarak log'a, Sentry'ye ve (DEBUG açıksa) HTTP yanıtına taşır.
        #
        # otp_hash özellikle kritik: tuzsuz SHA-256(6 hane), yani arama uzayı
        # 10^6. Hash'i gören biri kodu saniyeler içinde geri bulur ve
        # /verify-otp ile hesabı devralır. (Bu yüzden otp_hash'in kendisi de
        # artık HMAC ile üretiliyor — bkz. app/auth.py.)
        #
        # hide_parameters=True ile istisna metni parametre yerine
        # "[SQL parameters hidden due to hide_parameters=True]" yazar.
        # Bedeli: hata ayıklarken hangi değerin patlattığını göremeyiz; sorgu
        # metni ve istisna tipi yerinde kaldığı için bu kabul edilebilir.
        hide_parameters=True,
    )


engine = build_engine(_url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Tabloları (yoksa) oluşturur ve şema farklarını kapatır.

    create_all yalnızca OLMAYAN tabloyu doğurur; var olan tabloya sütun
    eklemez. Eksik sütunlar tek bir yerde, app.migrate içinde tanımlıdır —
    ikinci bir migrasyon yolu tutulursa iki liste kaçınılmaz olarak birbirinden
    ayrışır.
    """
    from app import models  # noqa: F401 — tabloların Base'e kaydolması için
    from app.migrate import run_migrations  # geç import: döngüyü önler

    Base.metadata.create_all(engine)
    run_migrations(engine)


def get_db():
    """İstek başına bir oturum açan FastAPI bağımlılığı."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
