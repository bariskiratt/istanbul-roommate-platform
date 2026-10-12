"""Swipe (beğen/geç) ve eşleşme uçları.

Eşleşme iki yoldan doğar:
1. Otomatik: A, B'nin ilanını beğenir ve B daha önce A'nın bir ilanını
   beğenmişse (karşılıklı beğeni).
2. Beğeniler ekranı: ilan sahibi, ilanını beğenen kişiyi kabul ederse.

Hinge tarzı beğeni: beğeni ilanın tamamına ya da belirli bir fotoğrafına /
kartına (soru-cevap) verilebilir, yanına kısa bir yorum yazılabilir. Yorum
mesaj gibi denetlenir ve şifreli saklanır; eşleşme olduğu anda sohbetin ilk
mesajı olur (_deliver_comments). Böylece yorum, eşleşmeyi doğuran yol hangisi
olursa olsun kaybolmaz.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app import content_limits, crypto, models, moderation
from app.auth import get_current_user
from app.db import get_db
from app.i18n import localized
from app.reports import require_admin

router = APIRouter(tags=["swipes"])

# Beğenilebilen kartlar. Kartın metnini (soru ve cevap) arayüz kendi dilinde
# ilanın ve sahibinin alanlarından üretir (frontend/src/lib/prompts.ts);
# sunucu yalnızca anahtarın bu kapalı listede olduğunu doğrular. Listede
# olmayan bir anahtar beğeniyi alan kişinin ekranında anlamsız bir kart
# olarak görünürdü.
PromptKey = Literal[
    "description",  # ilan sahibinin kendi yazdığı açıklama
    "sleep",        # uyku düzeni
    "habits",       # sigara, alkol, evcil hayvan
    "studies",      # bölüm ve sınıf
    "house_rules",  # ev ilanı: sigara / evcil hayvan kuralı
    "amenities",    # ev ilanı: eşyalı, asansör, internet …
]

# Hinge'deki yorum kutusu kadar: bir iki cümle. Uzun yazı sohbetin işi.
COMMENT_MAX_LENGTH = 300


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


class LikeTarget(BaseModel):
    """Beğeninin hedefi: ilanın bir fotoğrafı ya da bir kartı."""

    kind: Literal["photo", "prompt"]
    # İlan en fazla 6 fotoğraf taşır; dizinin ilanda olup olmadığına uç bakar.
    photo_index: int | None = Field(None, ge=0, le=5)
    prompt_key: PromptKey | None = None

    @model_validator(mode="after")
    def _check_ref(self):
        if self.kind == "photo" and self.photo_index is None:
            raise ValueError(localized("Fotoğraf beğenisinde photo_index zorunlu."))
        if self.kind == "prompt" and self.prompt_key is None:
            raise ValueError(localized("Kart beğenisinde prompt_key zorunlu."))
        return self


class SwipeIn(BaseModel):
    listing_id: int = Field(..., ge=1)
    direction: str = Field(..., pattern="^(like|pass)$")
    # İkisi de isteğe bağlı ve YALNIZCA beğenide anlamlı. Hedefsiz yorum
    # ilanın tamamına yazılmış sayılır.
    target: LikeTarget | None = None
    comment: str | None = Field(None, max_length=COMMENT_MAX_LENGTH)

    @model_validator(mode="after")
    def _like_only(self):
        if self.direction != "like" and (
            self.target is not None or (self.comment or "").strip()
        ):
            raise ValueError(
                localized("Hedef ve yorum yalnızca beğenide gönderilebilir.")
            )
        return self


class SwipeResult(BaseModel):
    matched: bool
    match_id: int | None = None


class DeckReset(BaseModel):
    deleted: int


class LikeTargetOut(BaseModel):
    """Beğenilen şey. Fotoğrafta, beğenildiği andaki adres döner."""

    kind: Literal["photo", "prompt"]
    photo_url: str | None = None
    prompt_key: str | None = None


class ReceivedLike(BaseModel):
    swipe_id: int
    user: UserPublic
    listing_id: int
    listing_title: str
    # None: ilanın tamamı beğenildi.
    target: LikeTargetOut | None = None
    comment: str | None = None
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


def _suspended_user_ids():
    """Askıdaki kullanıcı id'leri — beğeni/eşleşme listelerinden elenirler."""
    return select(models.User.id).where(models.User.is_suspended.is_(True))


def _prepare_comment(
    raw: str | None, user_id: int
) -> tuple[str | None, bool, str | None]:
    """Yorumu denetler; (şifreli metin, işaretli mi, gerekçeler) döner.

    Mesajla aynı kurallar (app.messages.send_message): sistem sabiti taklidi
    ve "block" sonucu reddedilir, "flag" sonucu yorum kabul edilir ama
    işareti saklanır. İşaret, yorum sohbete taşındığında mesaja geçer ve
    yönetici kuyruğuna oradan düşer.
    """
    text = (raw or "").strip()
    if not text:
        return None, False, None
    # Yorum, karşı tarafın Beğeniler kuyruğuna yazılan metindir: sınırsız
    # olsaydı tek hesap yüzlerce ilana yorum yağdırabilirdi (bkz. bulgu H3).
    content_limits.check("like_comment", user_id)
    if moderation.is_system_marker(text):
        raise HTTPException(
            status_code=422,
            detail=localized(moderation.SYSTEM_MARKER_REJECTION),
        )
    result = moderation.check(text, kind="message")
    if result.blocked:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{moderation.describe(result.reasons, subject='Yorumda')} "
                + localized("Yorumunu düzenleyip tekrar gönder.")
            ),
        )
    return crypto.encrypt(text), result.flagged, moderation.reasons_csv(result)


def _resolve_target(
    target: LikeTarget | None, listing: models.Listing
) -> tuple[str | None, str | None]:
    """Hedefi (target_kind, target_ref) çiftine çevirir.

    Fotoğrafta dizin değil ADRES saklanır ve adres ilanın kendisinden okunur:
    istemcinin gönderdiği bir adres beğeniyi alanın ekranına olduğu gibi
    basılırdı, yani herkes başkasının Beğeniler kuyruğuna istediği görseli
    koyabilirdi.
    """
    if target is None:
        return None, None
    if target.kind == "photo":
        photos = listing.photos or []
        if target.photo_index is None or target.photo_index >= len(photos):
            raise HTTPException(
                status_code=422, detail=localized("Beğenilen fotoğraf bu ilanda yok.")
            )
        return "photo", photos[target.photo_index]
    return "prompt", target.prompt_key


def _target_out(row: models.Swipe) -> dict | None:
    if row.target_kind == "photo":
        return {"kind": "photo", "photo_url": row.target_ref}
    if row.target_kind == "prompt":
        return {"kind": "prompt", "prompt_key": row.target_ref}
    return None


def _comment_out(row: models.Swipe) -> str | None:
    """Yorumu çözer. Çözülemeyen yorum gösterilmez: beğeni yine durur, ama
    "[unreadable]" yazan bir yorum kutusu kimseye bir şey anlatmaz."""
    text = crypto.decrypt(row.comment)
    if not text or text == crypto.UNREADABLE:
        return None
    return text


def _deliver_comments(
    db: Session, match: models.Match, user_x: int, user_y: int
) -> int:
    """İki kişinin birbirinin ilanlarına yazdığı yorumları sohbete taşır.

    Eşleşme HANGİ YOLDAN doğarsa doğsun (karşılıklı beğeni ya da Beğeniler
    ekranında kabul) çağrılır; Hinge'de olduğu gibi yorum sohbetin ilk
    mesajı olur. Kurallar:

    - Her yorum bir kez taşınır (comment_delivered). Eşleşme zaten varken
      gelen yeni yorumlu beğeni kabul edilince yalnızca o yeni yorum gelir.
    - Yanıtlanmış (ilan sahibinin "geç" dediği) beğeninin yorumu taşınmaz:
      ret edilen yorum, iki kişi başka bir ilandan eşleşse bile sohbete
      sızmamalı. Kabul yolu, bu yüzden beğeniyi yanıtlanmış saymadan ÖNCE
      burayı çağırır.
    - Şifreli metin olduğu gibi kopyalanır; denetim işareti mesaja geçer ve
      yönetici kuyruğuna oradan düşer.

    Çağıran, yeni swipe satırlarını önceden flush etmiş olmalı (oturum
    autoflush=False).
    """
    rows = db.scalars(
        select(models.Swipe)
        .join(models.Listing, models.Swipe.listing_id == models.Listing.id)
        .where(
            models.Swipe.direction == "like",
            models.Swipe.responded.is_(False),
            models.Swipe.comment.is_not(None),
            models.Swipe.comment_delivered.is_(False),
            or_(
                and_(
                    models.Swipe.swiper_id == user_x,
                    models.Listing.owner_id == user_y,
                ),
                and_(
                    models.Swipe.swiper_id == user_y,
                    models.Listing.owner_id == user_x,
                ),
            ),
        )
        .order_by(models.Swipe.created_at, models.Swipe.id)
    ).all()
    for row in rows:
        db.add(
            models.Message(
                match_id=match.id,
                sender_id=row.swiper_id,
                content=row.comment,
                is_flagged=bool(row.comment_flagged),
                flag_reasons=row.comment_flag_reasons,
            )
        )
        row.comment_delivered = True
    return len(rows)


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
    # Askıdaki sahibin ilanı listede görünmüyor; doğrudan id ile de
    # kaydırılamamalı, aksi hâlde askı yeni eşleşme doğurur.
    if (
        listing is None
        or not listing.is_active
        or (listing.owner is not None and listing.owner.is_suspended)
    ):
        raise HTTPException(status_code=404, detail=localized("İlan bulunamadı."))
    if listing.owner_id == user.id:
        raise HTTPException(
            status_code=400, detail=localized("Kendi ilanını kaydıramazsın.")
        )

    target_kind, target_ref = _resolve_target(payload.target, listing)
    comment, comment_flagged, comment_reasons = _prepare_comment(
        payload.comment, user.id
    )
    like_fields = {
        "target_kind": target_kind,
        "target_ref": target_ref,
        "comment": comment,
        "comment_flagged": comment_flagged,
        "comment_flag_reasons": comment_reasons,
        "comment_delivered": False,
    }

    existing = db.scalar(
        select(models.Swipe).where(
            models.Swipe.swiper_id == user.id,
            models.Swipe.listing_id == listing.id,
        )
    )
    if existing is not None:
        # Yalnızca karar değiştiyse günceller; aynı ilana tekrar tekrar like
        # atarak sahibin Beğeniler kuyruğunu şişirmek mümkün olmasın. Aynı
        # sebeple ikinci beğeni yorumu da DEĞİŞTİRMEZ: yoksa yanıtlanmış bir
        # beğeninin yorumu sessizce yeniden yazılabilirdi. (Deste karar
        # verilmiş ilanı zaten bir daha göstermiyor.)
        if existing.direction != payload.direction:
            existing.direction = payload.direction
            existing.responded = False
            # "geç"e dönen beğeninin hedefi ve yorumu da gider (alanların
            # hepsi None/False gelir, çünkü şema geçte ikisini de reddeder).
            for key, value in like_fields.items():
                setattr(existing, key, value)
    else:
        db.add(
            models.Swipe(
                swiper_id=user.id,
                listing_id=listing.id,
                direction=payload.direction,
                **like_fields,
            )
        )

    matched, match_id = False, None
    if (
        payload.direction == "like"
        and listing.owner_id is not None
        and _has_reverse_like(db, listing.owner_id, user.id)
    ):
        match, _ = _get_or_create_match(db, user.id, listing.owner_id, listing.id)
        db.flush()  # yeni swipe satırı _deliver_comments'in sorgusunda görünsün
        _deliver_comments(db, match, user.id, listing.owner_id)
        matched, match_id = True, match.id

    db.commit()
    return {"matched": matched, "match_id": match_id}


@router.delete("/api/swipes/mine", response_model=DeckReset)
def reset_my_deck(
    db: Session = Depends(get_db),
    user: models.User = Depends(require_admin),
):
    """Kendi kaydırma geçmişini siler; deste baştan gelir — yalnızca yönetici.

    Demo ve elde test için: kararlar silinince /api/listings?unswiped=1 tüm
    ilanları yeniden döndürür.

    EŞLEŞMELER VE SOHBETLER KORUNUR — silinen yalnızca Swipe kayıtlarıdır.
    Kullanıcı aynı ilanı tekrar beğenirse _get_or_create_match var olan
    eşleşmeyi bulur, ikinci bir eşleşme doğmaz ve mesaj geçmişi yerinde kalır.
    """
    deleted = (
        db.query(models.Swipe)
        .filter(models.Swipe.swiper_id == user.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"deleted": deleted}


@router.get("/api/swipes/received", response_model=list[ReceivedLike])
def received_likes(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """İlanlarımı beğenen, henüz cevaplamadığım kullanıcılar (en yeni önce)."""
    rows = db.scalars(
        select(models.Swipe)
        .options(  # kart başına ekstra sorgu atılmasın (N+1)
            selectinload(models.Swipe.swiper),
            selectinload(models.Swipe.listing),
        )
        .join(models.Listing, models.Swipe.listing_id == models.Listing.id)
        .where(
            models.Listing.owner_id == user.id,
            models.Swipe.direction == "like",
            models.Swipe.responded.is_(False),
            # Askıya alınan kullanıcının beğenisi kuyrukta durmaz.
            models.Swipe.swiper_id.not_in(_suspended_user_ids()),
        )
        .order_by(models.Swipe.created_at.desc(), models.Swipe.id.desc())
    ).all()
    return [
        {
            "swipe_id": s.id,
            "user": s.swiper,
            "listing_id": s.listing_id,
            "listing_title": s.listing.title,
            "target": _target_out(s),
            "comment": _comment_out(s),
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
    """Beğeniler ekranından kabul/ret. Kabul eşleşme yaratır.

    Askıdaki kullanıcının beğenisi bu uçtan İŞLENEMEZ (404). Gerekçe:

    - /api/swipes/received bu beğeniyi zaten listelemiyor; uç "yok" diyen
      listeyle tutarlı davranıyor. 403 seçilmedi, çünkü 403 "senin yetkin
      yok" demektir — oysa ilan sahibinin yetkisi var, ORTADA İŞLENECEK
      GEÇERLİ BİR BEĞENİ YOK.
    - Karşı tarafın askıda olduğu bilgisi sızmıyor (bkz. admin.py ilke 2-3).
    - Kabul kadar RET de engelleniyor: askı geri alınabilir bir karardır;
      ret responded=True yazıp beğeniyi kalıcı olarak yok etseydi, askı
      kalktığında geri gelmesi gereken beğeni geri gelmezdi.

    Eskiden bu kontrol yoktu: eski bir swipe_id ile askıdaki kullanıcıyla
    eşleşme yaratılabiliyordu. Kullanıcı "Eşleştiniz!" yanıtı alıyor ama
    eşleşme /api/matches'ten elendiği için hiçbir listede görünmüyordu
    (ölü eşleşme). /api/swipes ucu (swipe) bu kontrole zaten sahipti.
    """
    row = db.get(models.Swipe, swipe_id)
    if row is None or row.direction != "like":
        raise HTTPException(status_code=404, detail=localized("Beğeni bulunamadı."))
    if row.listing.owner_id != user.id:
        # 404, 403 DEĞİL: 403 "böyle bir beğeni var ama senin değil" derdi ve
        # id gezerek platformdaki beğenileri saymaya yarardı (bulgu L4).
        # Yanıt, olmayan bir id ile birebir aynı.
        raise HTTPException(status_code=404, detail=localized("Beğeni bulunamadı."))
    if row.swiper is not None and row.swiper.is_suspended:
        raise HTTPException(status_code=404, detail=localized("Beğeni bulunamadı."))

    matched, match_id = False, None
    if payload.accept:
        match, _ = _get_or_create_match(db, user.id, row.swiper_id, row.listing_id)
        # Yorum, beğeni yanıtlanmış sayılmadan ÖNCE taşınır; bkz.
        # _deliver_comments (yanıtlanmış beğeninin yorumu taşınmaz).
        _deliver_comments(db, match, user.id, row.swiper_id)
        matched, match_id = True, match.id
    row.responded = True

    db.commit()
    return {"matched": matched, "match_id": match_id}


@router.get("/api/matches", response_model=list[MatchOut])
def my_matches(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    rows = db.scalars(
        select(models.Match)
        .options(
            selectinload(models.Match.user_a),
            selectinload(models.Match.user_b),
            selectinload(models.Match.listing),
        )
        .where(
            or_(
                models.Match.user_a_id == user.id,
                models.Match.user_b_id == user.id,
            ),
            # Askıdaki karşı tarafla sohbet listede görünmez; askı kalkınca
            # eşleşme de mesajlar da yerinde durur. Sohbetin kendisi id ile
            # hâlâ OKUNABİLİR (geçmiş kaybolmasın), ama yeni mesaj kabul
            # edilmez — bkz. app/messages.py send_message (403).
            models.Match.user_a_id.not_in(_suspended_user_ids()),
            models.Match.user_b_id.not_in(_suspended_user_ids()),
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
                # Mesajlar şifreli saklanır; önizleme için çözülür.
                "last_message": crypto.decrypt(last.content) if last else None,
                "last_message_at": last.created_at if last else None,
            }
        )
    return result
