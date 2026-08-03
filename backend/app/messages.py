"""Eşleşme içi mesajlaşma uçları.

Gerçek zamanlılık için istemci kısa aralıkla listeyi yeniler (polling);
WebSocket bu ölçek için henüz gerekmedi.

Mesajlar veritabanına şifreli yazılır (app.crypto) ve yanıtta çözülerek
düz metin döner. Şifreleme sunucuda saklanan veriyi korur; anahtar
sunucuda olduğu için UÇTAN UCA şifreleme değildir.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import content_limits, crypto, models, moderation
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


def _to_out(row: models.Message) -> dict:
    """Satırı yanıt sözlüğüne çevirir; içerik burada çözülür."""
    return {
        "id": row.id,
        "match_id": row.match_id,
        "sender_id": row.sender_id,
        "content": crypto.decrypt(row.content) or "",
        "created_at": row.created_at,
    }


def _require_participant(
    match_id: int, user: models.User, db: Session
) -> models.Match:
    """Eşleşmeyi verir; taraf olmayana YOK muamelesi yapar.

    Taraf olmayana 404 döner, 403 DEĞİL: 403 "bu eşleşme var ama senin değil"
    demektir ve id gezerek hangi eşleşmelerin var olduğunu saymaya yarardı
    (bulgu L4). Kendi eşleşmesi olmayan biri için var olan ve olmayan id
    artık ayırt edilemez.
    """
    match = db.get(models.Match, match_id)
    if match is None or user.id not in (match.user_a_id, match.user_b_id):
        raise HTTPException(status_code=404, detail="Eşleşme bulunamadı.")
    return match


def _other_user(match: models.Match, user: models.User, db: Session) -> models.User | None:
    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    return db.get(models.User, other_id)


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
        return [_to_out(row) for row in rows]

    # Son N mesaj: tersten al, kronolojik sırala
    rows = db.scalars(
        stmt.order_by(models.Message.created_at.desc(), models.Message.id.desc())
        .limit(limit)
    ).all()
    return [_to_out(row) for row in reversed(rows)]


@router.post("/{match_id}/messages", status_code=201, response_model=MessageOut)
def send_message(
    match_id: int,
    payload: MessageIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    match = _require_participant(match_id, user, db)
    # Mesaj yağmuruna karşı kullanıcı başına sınır (bulgu H3). Taraf kontrolü
    # ÖNCE koşar: sınır, yabancı bir eşleşmeye yazmaya çalışan için de sayaç
    # tutup "bu id var mı" sorusuna dolaylı cevap vermesin.
    content_limits.check("message_send", user.id)

    # Askıdaki kullanıcıya yeni mesaj gitmez. Sohbet /api/matches listesinde
    # zaten görünmüyor; buna rağmen mesaj kabul etmek karşı tarafın hiç
    # okumayacağı (giriş yapamıyor) bir mesajı gönderene "iletildi" göstermek
    # olurdu. GEÇMİŞİN OKUNMASI ENGELLENMEZ — yalnızca yeni mesaj engellenir.
    other = _other_user(match, user, db)
    if other is not None and other.is_suspended:
        raise HTTPException(
            status_code=403,
            detail="Bu hesap askıya alındı; şu an mesaj gönderilemiyor.",
        )

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz.")

    # Kullanıcı sistemin ağzından konuşamaz: "[removed_by_moderation]" ya da
    # "[unreadable]" yazan bir mesaj arayüzde sistem metni olarak basılırdı
    # (bkz. moderation.SYSTEM_MARKERS).
    if moderation.is_system_marker(content):
        raise HTTPException(
            status_code=422, detail=moderation.SYSTEM_MARKER_REJECTION
        )

    result = moderation.check(content, kind="message")
    if result.blocked:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{moderation.describe(result.reasons)} "
                "Mesajını düzenleyip tekrar gönder."
            ),
        )

    row = models.Message(
        match_id=match_id,
        sender_id=user.id,
        content=crypto.encrypt(content),
        is_flagged=result.flagged,
        flag_reasons=moderation.reasons_csv(result),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)
