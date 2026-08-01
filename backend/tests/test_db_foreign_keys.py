"""SQLite yabancı anahtar zorlaması uygulamanın kendisinde açık mı.

Bu dosya bir DAVRANIŞI değil, bir ORTAM AYARINI korur. Ayar test kurulumuna
(conftest) taşınırsa testler yeşil kalır ama çalışan sunucu Postgres'ten
sessizce ayrışır: yanlış silme sırası yerelde geçer, üretimde IntegrityError
verir. Bu yüzden dinleyicinin app/db.py içinde olduğu burada doğrulanır.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.db import Base, engine


def test_uygulamanin_kendi_motorunda_fk_acik():
    """Sunucunun kullandığı motor: PRAGMA foreign_keys = 1."""
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_yeni_kurulan_sqlite_motorunda_da_fk_acik():
    """Dinleyici Engine sınıfına bağlı olduğu için her motorda geçerli.

    conftest artık kendi PRAGMA'sını kurmuyor; bu doğrulama geçiyorsa ayar
    gerçekten app/db.py'den geliyor demektir.
    """
    fresh = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with fresh.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_fk_zorlamasi_gercekten_calisiyor():
    """PRAGMA okunuyor olması yetmez — ihlal gerçekten patlamalı."""
    fresh = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(fresh)
    Session = sessionmaker(bind=fresh, autoflush=False, expire_on_commit=False)

    db = Session()
    # Var olmayan bir kullanıcıya rapor bağlamak kısıtı ihlal eder.
    db.add(
        models.Report(
            reporter_id=999_999,
            target_type="listing",
            target_id=1,
            reason="spam",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_kullanici_silmek_asili_rapor_birakamaz():
    """Raporu duran bir kullanıcıyı doğrudan silmek kısıta takılır.

    app/auth.py'deki hesap silme akışının raporları neden ÖNCE temizlemek
    zorunda olduğunu gösterir; sıra bozulursa bu kısıt onu yakalar.
    """
    fresh = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(fresh)
    Session = sessionmaker(bind=fresh, autoflush=False, expire_on_commit=False)

    db = Session()
    user = models.User(email="raporcu@uni.edu.tr", name="Raporcu")
    db.add(user)
    db.commit()
    db.add(
        models.Report(
            reporter_id=user.id,
            target_type="listing",
            target_id=1,
            reason="spam",
        )
    )
    db.commit()

    db.delete(user)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
