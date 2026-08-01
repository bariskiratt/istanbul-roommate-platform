"""Kullanıcı şikâyetleri (raporlama).

Otomatik içerik denetimi (app.moderation) her şeyi yakalayamaz; kullanıcılar
ilan, kullanıcı veya mesaj raporlayabilir. Raporlar yalnızca yöneticiye
(config.ADMIN_EMAILS) listelenir ve orada çözüldü olarak işaretlenir.

Aynı kullanıcının aynı hedefi tekrar tekrar raporlaması engellenir
(models.Report üzerindeki UniqueConstraint + burada 409).
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/api/reports", tags=["reports"])

TargetType = Literal["listing", "user", "message"]
ReportReason = Literal[
    "spam",
    "dolandiricilik",
    "taciz",
    "uygunsuz_icerik",
    "sahte_ilan",
    "diger",
]

# Kapalı liste — istemci /api/reports/reasons ile çeker, elle kopyalamaz.
REPORT_REASONS: tuple[str, ...] = (
    "spam",
    "dolandiricilik",
    "taciz",
    "uygunsuz_icerik",
    "sahte_ilan",
    "diger",
)

# Hedef türü -> tablo. Raporlanan içeriğin gerçekten var olduğunu doğrular.
_TARGET_MODELS = {
    "listing": models.Listing,
    "user": models.User,
    "message": models.Message,
}


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    """Yalnız yönetici uçları için bağımlılık."""
    if not user.is_admin:
        raise HTTPException(
            status_code=403, detail="Bu işlem için yönetici yetkisi gerekiyor."
        )
    return user


def _existing_report(
    db: Session, reporter_id: int, target_type: str, target_id: int
) -> bool:
    """Bu kullanıcı bu hedefi daha önce raporlamış mı."""
    return db.scalar(
        select(models.Report.id).where(
            models.Report.reporter_id == reporter_id,
            models.Report.target_type == target_type,
            models.Report.target_id == target_id,
        )
    ) is not None


class ReportIn(BaseModel):
    target_type: TargetType
    target_id: int = Field(..., ge=1)
    reason: ReportReason
    note: str | None = Field(None, max_length=500)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reporter_id: int
    target_type: str
    target_id: int
    reason: str
    note: str | None
    created_at: datetime
    resolved: bool
    resolution_note: str | None
    resolved_by: int | None = None
    resolved_at: datetime | None = None


@router.get("/reasons", response_model=list[str])
def report_reasons():
    """Kapalı sebep listesi (etiketleri istemci kendi dilinde gösterir)."""
    return list(REPORT_REASONS)


@router.post("", status_code=201, response_model=ReportOut)
def create_report(
    payload: ReportIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Rapor oluşturma giriş ister — anonim ihbar yağmuruna kapalı."""
    if payload.target_type == "user" and payload.target_id == user.id:
        raise HTTPException(status_code=400, detail="Kendini raporlayamazsın.")

    target = db.get(_TARGET_MODELS[payload.target_type], payload.target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Raporlanacak içerik bulunamadı.")

    if _existing_report(db, user.id, payload.target_type, payload.target_id):
        raise HTTPException(
            status_code=409, detail="Bu içeriği zaten raporladın."
        )

    note = payload.note.strip() if payload.note else None
    row = models.Report(
        reporter_id=user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=payload.reason,
        note=note or None,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Yukarıdaki SELECT ile bu INSERT arasında aynı kullanıcı aynı hedefi
        # ikinci kez raporlarsa (çift tıklama, paralel istek) tekillik kısıtı
        # burada patlar. Yarışın kaybedeni de kullanıcı açısından "zaten
        # raporladın" durumudur; 500 yerine 409 döner.
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Bu içeriği zaten raporladın."
        ) from None
    db.refresh(row)
    return row


@router.get("", response_model=list[ReportOut])
def list_reports(
    resolved: bool | None = Query(
        None, description="Çözülmüş/çözülmemiş filtresi; boş bırakılırsa hepsi"
    ),
    target_type: TargetType | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Raporlar, en yeni önce — yalnızca yönetici."""
    stmt = select(models.Report).order_by(
        models.Report.created_at.desc(), models.Report.id.desc()
    )
    if resolved is not None:
        stmt = stmt.where(models.Report.resolved.is_(resolved))
    if target_type is not None:
        stmt = stmt.where(models.Report.target_type == target_type)
    return db.scalars(stmt.limit(limit)).all()


# NOT: Raporu çözme ucu buradan app/admin.py'ye TAŞINDI
# (PATCH /api/admin/reports/{id}). Tek bir yönetici yüzeyi olsun diye iki ayrı
# uç bırakılmadı; yeni uç ayrıca resolved_by / resolved_at yazar.
