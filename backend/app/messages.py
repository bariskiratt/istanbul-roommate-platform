"""Eşleşme içi mesajlaşma uçları.

Gerçek zamanlılık için istemci kısa aralıkla listeyi yeniler (polling);
WebSocket bu ölçek için henüz gerekmedi.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(prefix="/api/matches", tags=["messages"])


class MessageIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    sender_id: int
    content: str
    created_at: datetime


def _require_participant(
    match_id: int, user: models.User, db: Session
) -> models.Match:
    match = db.get(models.Match, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Eşleşme bulunamadı.")
    if user.id not in (match.user_a_id, match.user_b_id):
        raise HTTPException(status_code=403, detail="Bu eşleşmenin tarafı değilsin.")
    return match


@router.get("/{match_id}/messages", response_model=list[MessageOut])
def list_messages(
    match_id: int,
    limit: int = Query(200, ge=1, le=500, description="En fazla mesaj sayısı"),
    after_id: int | None = Query(
        None, ge=1, description="Yalnızca bu id'den sonrakiler (artımlı çekim)"
    ),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Eşleşmenin mesajları, eskiden yeniye.

    Varsayılan: son `limit` mesaj. İstemci polling'de `after_id` ile yalnız
    yeni mesajları çekebilir; tüm geçmiş her turda taşınmaz.
    """
    _require_participant(match_id, user, db)

    stmt = select(models.Message).where(models.Message.match_id == match_id)
    if after_id is not None:
        rows = db.scalars(
            stmt.where(models.Message.id > after_id)
            .order_by(models.Message.created_at, models.Message.id)
            .limit(limit)
        ).all()
        return rows

    # Son N mesaj: tersten al, kronolojik sırala
    rows = db.scalars(
        stmt.order_by(models.Message.created_at.desc(), models.Message.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


@router.post("/{match_id}/messages", status_code=201, response_model=MessageOut)
def send_message(
    match_id: int,
    payload: MessageIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_participant(match_id, user, db)
    row = models.Message(
        match_id=match_id, sender_id=user.id, content=payload.content.strip()
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
