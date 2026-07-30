"""Swipe (beğen/geç) ve eşleşme uçları.

Eşleşme iki yoldan doğar:
1. Otomatik: A, B'nin ilanını beğenir ve B daha önce A'nın bir ilanını
   beğenmişse (karşılıklı beğeni).
2. Beğeniler ekranı: ilan sahibi, ilanını beğenen kişiyi kabul ederse.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user
from app.db import get_db

router = APIRouter(tags=["swipes"])


# ---- şemalar ----

class UserPublic(BaseModel):
    """Başka kullanıcılara gösterilen profil (e-posta gibi alanlar hariç)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    university: str | None
    department: str | None
    year: int | None
    budget_min: int | None
    budget_max: int | None
    smoking: bool | None
    pets: bool | None
    alcohol: bool | None
    sleep_schedule: str | None
    preferred_districts: list[str]
    bio: str
    photos: list[str]


class SwipeIn(BaseModel):
    listing_id: int = Field(..., ge=1)
    direction: str = Field(..., pattern="^(like|pass)$")


class SwipeResult(BaseModel):
    matched: bool
    match_id: int | None = None


class ReceivedLike(BaseModel):
    swipe_id: int
    user: UserPublic
    listing_id: int
    listing_title: str
    created_at: datetime


class RespondIn(BaseModel):
    accept: bool


class MatchOut(BaseModel):
    id: int
    other_user: UserPublic
    listing_id: int | None
    listing_title: str | None
    created_at: datetime
    last_message: str | None = None
    last_message_at: datetime | None = None


# ---- yardımcılar ----

def _get_or_create_match(
    db: Session, user_x: int, user_y: int, listing_id: int | None
) -> tuple[models.Match, bool]:
    a, b = sorted((user_x, user_y))
    existing = db.scalar(
        select(models.Match).where(
            models.Match.user_a_id == a, models.Match.user_b_id == b
        )
    )
    if existing is not None:
        return existing, False
    match = models.Match(user_a_id=a, user_b_id=b, listing_id=listing_id)
    db.add(match)
    db.flush()
    return match, True


def _has_reverse_like(db: Session, from_user: int, toward_user: int) -> bool:
    """from_user, toward_user'ın herhangi bir ilanını beğenmiş mi?"""
    return db.scalar(
        select(models.Swipe.id)
        .join(models.Listing, models.Swipe.listing_id == models.Listing.id)
        .where(
            models.Swipe.swiper_id == from_user,
            models.Swipe.direction == "like",
            models.Listing.owner_id == toward_user,
        )
        .limit(1)
    ) is not None


# ---- uçlar ----

@router.post("/api/swipes", response_model=SwipeResult)
def swipe(
    payload: SwipeIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    listing = db.get(models.Listing, payload.listing_id)
    if listing is None or not listing.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if listing.owner_id == user.id:
        raise HTTPException(status_code=400, detail="Kendi ilanını kaydıramazsın.")

    existing = db.scalar(
        select(models.Swipe).where(
            models.Swipe.swiper_id == user.id,
            models.Swipe.listing_id == listing.id,
        )
    )
    if existing is not None:
        existing.direction = payload.direction
        existing.responded = False
    else:
        db.add(
            models.Swipe(
                swiper_id=user.id,
                listing_id=listing.id,
                direction=payload.direction,
            )
        )

    matched, match_id = False, None
    if (
        payload.direction == "like"
        and listing.owner_id is not None
        and _has_reverse_like(db, listing.owner_id, user.id)
    ):
        match, _ = _get_or_create_match(db, user.id, listing.owner_id, listing.id)
        matched, match_id = True, match.id

    db.commit()
    return {"matched": matched, "match_id": match_id}


@router.get("/api/swipes/received", response_model=list[ReceivedLike])
def received_likes(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """İlanlarımı beğenen, henüz cevaplamadığım kullanıcılar (en yeni önce)."""
    rows = db.scalars(
        select(models.Swipe)
        .join(models.Listing, models.Swipe.listing_id == models.Listing.id)
        .where(
            models.Listing.owner_id == user.id,
            models.Swipe.direction == "like",
            models.Swipe.responded.is_(False),
        )
        .order_by(models.Swipe.created_at.desc(), models.Swipe.id.desc())
    ).all()
    return [
        {
            "swipe_id": s.id,
            "user": s.swiper,
            "listing_id": s.listing_id,
            "listing_title": s.listing.title,
            "created_at": s.created_at,
        }
        for s in rows
    ]


@router.post("/api/swipes/{swipe_id}/respond", response_model=SwipeResult)
def respond_to_like(
    swipe_id: int,
    payload: RespondIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Beğeniler ekranından kabul/ret. Kabul eşleşme yaratır."""
    row = db.get(models.Swipe, swipe_id)
    if row is None or row.direction != "like":
        raise HTTPException(status_code=404, detail="Beğeni bulunamadı.")
    if row.listing.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Bu beğeni senin ilanına değil.")

    row.responded = True
    matched, match_id = False, None
    if payload.accept:
        match, _ = _get_or_create_match(db, user.id, row.swiper_id, row.listing_id)
        matched, match_id = True, match.id

    db.commit()
    return {"matched": matched, "match_id": match_id}


@router.get("/api/matches", response_model=list[MatchOut])
def my_matches(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(
        select(models.Match)
        .where(
            or_(
                models.Match.user_a_id == user.id,
                models.Match.user_b_id == user.id,
            )
        )
        .order_by(models.Match.created_at.desc(), models.Match.id.desc())
    ).all()

    def _last_message(match_id: int) -> models.Message | None:
        return db.scalar(
            select(models.Message)
            .where(models.Message.match_id == match_id)
            .order_by(models.Message.created_at.desc(), models.Message.id.desc())
            .limit(1)
        )

    result = []
    for m in rows:
        last = _last_message(m.id)
        result.append(
            {
                "id": m.id,
                "other_user": m.user_b if m.user_a_id == user.id else m.user_a,
                "listing_id": m.listing_id,
                "listing_title": m.listing.title if m.listing else None,
                "created_at": m.created_at,
                "last_message": last.content if last else None,
                "last_message_at": last.created_at if last else None,
            }
        )
    return result
