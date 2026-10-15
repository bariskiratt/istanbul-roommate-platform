"""Engelleme ve eşleşmeyi kaldırma.

Eskiden taciz durumunda tek çare şikâyet edip yöneticiyi beklemekti: kişi ne
sohbeti kapatabiliyor ne de karşı tarafın onu tekrar görmesini
engelleyebiliyordu.

Tek kavram var: ENGEL (models.Block). "Eşleşmeyi kaldır" da bir engeldir;
Hinge ve Bumble'da olduğu gibi kaldırılan eşleşme bir daha karşına çıkmaz.
Etki iki yönlüdür (engelleyen ve engellenen için aynı):

- destede birbirinin ilanı görünmez, doğrudan id ile kaydırılamaz;
- birbirinin beğenisi Beğeniler kuyruğuna düşmez, eski beğeni kabul edilemez;
- aradaki eşleşme ikisinin listesinden de kalkar, mesajlar okunamaz ve
  gönderilemez (404, eşleşme yokmuş gibi).

Hiçbir satır silinmez. Engel kaldırılınca (DELETE /api/blocks/{id}) her şey
olduğu yerden devam eder; taciz şikâyeti varsa yönetici mesajları görebilir.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, union
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user
from app.db import get_db
from app.i18n import localized

router = APIRouter(prefix="/api/blocks", tags=["blocks"])


def blocked_ids(user_id: int):
    """Bu kullanıcıyla arasında engel olan herkesin id'leri (iki yön).

    Sorgularda `.not_in(blocked_ids(uid))` olarak kullanılır.
    """
    return union(
        select(models.Block.blocked_id).where(models.Block.blocker_id == user_id),
        select(models.Block.blocker_id).where(models.Block.blocked_id == user_id),
    )


def is_blocked(db: Session, a: int, b: int) -> bool:
    """a ile b arasında (hangi yönde olursa olsun) engel var mı?"""
    return db.scalar(
        select(models.Block.id)
        .where(
            ((models.Block.blocker_id == a) & (models.Block.blocked_id == b))
            | ((models.Block.blocker_id == b) & (models.Block.blocked_id == a))
        )
        .limit(1)
    ) is not None


class BlockIn(BaseModel):
    user_id: int = Field(..., ge=1)


class BlockedUser(BaseModel):
    user_id: int
    name: str
    university: str | None
    photo: str | None
    created_at: datetime


@router.post("", status_code=204)
def block_user(
    payload: BlockIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Kullanıcıyı engeller. Zaten engelliyse de 204 (tekrar basmak zararsız).

    Var olmayan id de 204 alır ve hiçbir şey yazılmaz: farklı yanıt, id
    gezerek hangi hesapların var olduğunu saymaya yarardı (bkz. bulgu L4).
    """
    if payload.user_id == user.id:
        raise HTTPException(
            status_code=400, detail=localized("Kendini engelleyemezsin.")
        )
    if db.get(models.User, payload.user_id) is None:
        return Response(status_code=204)
    exists = db.scalar(
        select(models.Block.id).where(
            models.Block.blocker_id == user.id,
            models.Block.blocked_id == payload.user_id,
        )
    )
    if exists is None:
        db.add(models.Block(blocker_id=user.id, blocked_id=payload.user_id))
        try:
            db.commit()
        except IntegrityError:  # aynı anda iki istek: ikincisi zaten var
            db.rollback()
    return Response(status_code=204)


@router.get("", response_model=list[BlockedUser])
def my_blocks(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Engellediğim kişiler (en yeni önce). Beni engelleyenler listelenmez."""
    rows = db.scalars(
        select(models.Block)
        .options(selectinload(models.Block.blocked))
        .where(models.Block.blocker_id == user.id)
        .order_by(models.Block.created_at.desc(), models.Block.id.desc())
    ).all()
    return [
        {
            "user_id": row.blocked_id,
            "name": row.blocked.name,
            "university": row.blocked.university,
            "photo": (row.blocked.photos or [None])[0],
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.delete("/{user_id}", status_code=204)
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Engeli kaldırır. Yalnızca KENDİ koyduğun engel kalkar; karşı taraf da
    seni engellediyse o engel durur."""
    db.query(models.Block).filter(
        models.Block.blocker_id == user.id, models.Block.blocked_id == user_id
    ).delete(synchronize_session=False)
    db.commit()
    return Response(status_code=204)
