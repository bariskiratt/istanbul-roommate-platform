"""Yönetici (moderasyon) uçları — /api/admin/*.

Tasarım ilkeleri:

1. EYLEMLER GERİ ALINABİLİR — ve geri almanın gerçek bir yolu vardır.
   Hiçbir uç kayıt silmez:
     - kullanıcı askıya alınır       -> POST /users/{id}/unsuspend
     - ilan yayından kaldırılır      -> POST /listing/{id}/restore
     - mesajın metni sabitle örtülür -> POST /message/{id}/restore
   Kaldırılan içerik BULUNABİLİR kalır: GET /flagged?status=removed.
   (Bu ikisi olmadan "geri alınabilir" sözü boştu: kaldırılan ilan hiçbir
   listede görünmediği ve is_active'i True yapan bir uç bulunmadığı için
   yanlış karar kalıcıydı. Mesajda ise metin üzerine yazılıyordu; artık
   models.Message.original_content'e taşınıyor.)
   TEK İSTİSNA — bu sütunlar gelmeden ÖNCE kaldırılmış mesajların metni
   gerçekten kaybolmuştur; onlarda restore metni geri getiremez. O kayıtlarda
   restore hiçbir şeyi değiştirmez ve `restored:false` döner: kayıt
   Kaldırılanlar kuyruğunda BULUNABİLİR kalsın diye bayrak indirilmez.
2. BİLDİRENİN KİMLİĞİ BİLDİRİLENE GÖSTERİLMEZ. Bu uçlar yalnızca yöneticiye
   açıktır; raporun reporter bilgisi buradan dışarı sızmaz.
3. YÖNETİCİ YALNIZCA KARAR İÇİN GEREKENİ GÖRÜR. Raporlanan mesajın metni
   döner, sohbetin tamamı DÖNMEZ. Kullanıcı listesi suspended filtresi
   ZORUNLU ister ve e-postayı yalnız askıdaki hesaplar için döner.
4. HER EYLEM KAYDEDİLİR: resolved_by/resolved_at, reviewed_by/reviewed_at,
   suspended_by/suspended_at. Geri alma da bir eylemdir: ilan/mesaj geri
   alınırken review_note'a not yazılır, askı kaldırılırken
   unsuspended_by/unsuspended_at yazılır ve gerekçe silinmeyip
   last_suspension_reason'a taşınır.

Tüm uçlar require_admin ile korunur: girişsiz 401, admin olmayan 403.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import crypto, models, moderation
from app.db import get_db
from app.reports import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

TargetType = Literal["listing", "user", "message"]
FlagKind = Literal["listing", "message"]

# Yönetici bir mesajı "kaldır" ile incelediğinde içeriğin yerine yazılan sabit.
# Satır SİLİNMEZ — silinirse sohbet akışındaki sıra ve bağlam bozulur.
# Değer app.moderation'da tanımlıdır; arayüz onu tanıyıp kendi dilinde bir
# karşılık basar (bkz. crypto.UNREADABLE ile aynı desen).
REMOVED_CONTENT = moderation.REMOVED_CONTENT


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# şemalar
# ---------------------------------------------------------------------------

class SummaryOut(BaseModel):
    open_reports: int
    flagged_listings: int
    flagged_messages: int
    suspended_users: int
    total_users: int
    active_listings: int


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # Askıdaki hesaplarda dolu, diğerlerinde None. Askıyı kaldırırken doğru
    # kişiye baktığını doğrulamak için gerekiyor; tüm kullanıcı tabanının
    # e-postası hiçbir ekranda gerekmiyor (bkz. ilke 3).
    email: str | None = None
    name: str
    university: str | None
    is_admin: bool = False
    is_suspended: bool = False
    suspended_at: datetime | None = None
    suspended_reason: str | None = None
    suspended_by: int | None = None
    # Askının KALDIRILMASININ izi (bkz. ilke 4). Askı kalkınca gerekçe
    # silinmez, last_suspension_reason'a taşınır; böylece "bu hesap daha önce
    # askıya alınmış mıydı, kim geri aldı" sorusu cevaplanabilir kalır.
    unsuspended_at: datetime | None = None
    unsuspended_by: int | None = None
    last_suspension_reason: str | None = None
    created_at: datetime


class SuspendIn(BaseModel):
    """Askı gerekçesi. Gövde tümüyle atlanabilir (sebepsiz askı)."""

    reason: str | None = Field(None, max_length=500)


class AdminReportOut(BaseModel):
    """Karar vermeye yetecek bağlamı taşıyan rapor satırı."""

    id: int
    reason: str
    note: str | None
    created_at: datetime
    resolved: bool
    resolution_note: str | None
    resolved_by: int | None
    resolved_at: datetime | None
    reporter_id: int
    reporter_name: str | None
    target_type: str
    target_id: int
    # Hedef özeti. Hedef silinmişse {"kind":..,"id":..,"deleted":true} döner —
    # null DEĞİL, uç da patlamaz. Anahtarlar için _target_summary'ye bak.
    target: dict


class ReportResolveIn(BaseModel):
    resolved: bool = True
    resolution_note: str | None = Field(None, max_length=500)


class FlaggedOut(BaseModel):
    """İlan ve mesaj işaretlemeleri için ortak satır biçimi."""

    kind: FlagKind
    id: int
    title: str | None  # ilan başlığı; mesajda None
    # İlan açıklaması / mesaj metni (çözülmüş). status=removed kuyruğunda
    # mesajın KALDIRILAN ORİJİNAL metni döner — yönetici neyi geri
    # alacağını görmeden karar veremez.
    content: str
    district: str | None  # yalnız ilan
    author_id: int | None
    author_name: str | None
    match_id: int | None  # yalnız mesaj
    is_active: bool | None  # yalnız ilan
    moderation_removed: bool
    # Yalnız ilan: kaldırma ANINDAKİ yayın durumu. Geri alma buraya döner,
    # yani bu alan False ise "geri alırsan ilan yayına GİRMEZ, kapalı kalır"
    # demektir (sahibi ilanı zaten kendi kapatmıştı). Arayüz Kaldırılanlar
    # kuyruğunda bunu okuyup yöneticiyi önceden uyarır.
    # None = mesaj satırı, ya da bu sütun eklenmeden önce kaldırılmış eski
    # ilan (önceki durum bilinmiyor; geri alma yayına alır).
    active_before_removal: bool | None = None
    flag_reasons: list[str]
    flag_reasons_text: str | None
    # Kaldırma kararının izi (status=removed kuyruğunda dolu olur).
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    created_at: datetime


class ReviewIn(BaseModel):
    action: Literal["clear", "remove"]
    note: str | None = Field(None, max_length=500)


class ReviewOut(BaseModel):
    kind: FlagKind
    id: int
    action: Literal["clear", "remove"]
    is_flagged: bool
    is_active: bool | None
    moderation_removed: bool
    content_removed: bool
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_note: str | None


class RestoreIn(BaseModel):
    """Geri alma notu. Gövde tümüyle atlanabilir (notsuz geri alma)."""

    note: str | None = Field(None, max_length=500)


class RestoreOut(BaseModel):
    kind: FlagKind
    id: int
    # Kaldırma gerçekten geri alındı mı. Neredeyse her zaman True; tek
    # istisna, metni kurtarılamayan eski mesaj kaydıdır (bkz.
    # content_recoverable). O durumda hiçbir alan değişmez ve False döner —
    # uç "geri aldım" demez.
    restored: bool
    # Yalnız ilan. Kaldırmadan önceki durum: yayındaydıysa True, sahibi zaten
    # kapatmışsa False (geri alma sahibin kararını ezmez).
    is_active: bool | None
    moderation_removed: bool
    # Yalnız mesaj: kaldırılan metin SAKLANMIŞ MI (original_content dolu mu).
    # False = kayıt bu sütunlar eklenmeden önce kaldırılmış, metin gerçekten
    # kayıp. İlanda None.
    content_recoverable: bool | None = None
    # Yalnız mesaj: kullanıcı artık metni OKUYABİLİYOR mu. Alanın dolu
    # olmasına DEĞİL, çözülen değere bakar: anahtar kaybolmuş/dönmüşse
    # geri konan içerik crypto.UNREADABLE'dır ve burası False döner.
    # (Eskiden yalnızca "alan dolu mu" bakılıyordu; arayüz "Mesajın metni
    # geri kondu." derken kullanıcı [unreadable] görüyordu.)
    content_restored: bool | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_note: str | None


# ---------------------------------------------------------------------------
# yardımcılar
# ---------------------------------------------------------------------------

def _count(db: Session, stmt) -> int:
    return db.scalar(select(func.count()).select_from(stmt.subquery())) or 0


def _deleted_target(target_type: str, target_id: int) -> dict:
    """Hedef artık yok. Uç patlamaz; yönetici durumu görür ve raporu kapatır."""
    return {"kind": target_type, "id": target_id, "deleted": True}


def _listing_summary(row: models.Listing) -> dict:
    return {
        "kind": "listing",
        "id": row.id,
        "deleted": False,
        "title": row.title,
        "district": row.district,
        "is_active": bool(row.is_active),
        "is_flagged": bool(row.is_flagged),
        "owner_id": row.owner_id,
        "owner_name": row.owner.name if row.owner else None,
    }


def _user_summary(row: models.User) -> dict:
    return {
        "kind": "user",
        "id": row.id,
        "deleted": False,
        "name": row.name,
        "university": row.university,
        "is_suspended": bool(row.is_suspended),
    }


def _message_summary(row: models.Message) -> dict:
    # Yalnızca raporlanan mesajın kendisi; sohbet geçmişi burada DÖNMEZ.
    return {
        "kind": "message",
        "id": row.id,
        "deleted": False,
        "content": crypto.decrypt(row.content) or "",
        "sender_id": row.sender_id,
        "sender_name": row.sender.name if row.sender else None,
        "match_id": row.match_id,
        "is_flagged": bool(row.is_flagged),
        "created_at": row.created_at,
    }


def _load_targets(db: Session, reports: list[models.Report]) -> dict:
    """Raporların hedeflerini tipe göre TOPLU çeker (satır başına sorgu yok)."""
    ids: dict[str, set[int]] = {"listing": set(), "user": set(), "message": set()}
    for report in reports:
        if report.target_type in ids:
            ids[report.target_type].add(report.target_id)

    found: dict[tuple[str, int], dict] = {}

    if ids["listing"]:
        rows = db.scalars(
            select(models.Listing)
            .options(selectinload(models.Listing.owner))
            .where(models.Listing.id.in_(ids["listing"]))
        ).all()
        found |= {("listing", r.id): _listing_summary(r) for r in rows}
    if ids["user"]:
        rows = db.scalars(
            select(models.User).where(models.User.id.in_(ids["user"]))
        ).all()
        found |= {("user", r.id): _user_summary(r) for r in rows}
    if ids["message"]:
        rows = db.scalars(
            select(models.Message)
            .options(selectinload(models.Message.sender))
            .where(models.Message.id.in_(ids["message"]))
        ).all()
        found |= {("message", r.id): _message_summary(r) for r in rows}
    return found


def _report_row(report: models.Report, targets: dict) -> dict:
    return {
        "id": report.id,
        "reason": report.reason,
        "note": report.note,
        "created_at": report.created_at,
        "resolved": bool(report.resolved),
        "resolution_note": report.resolution_note,
        "resolved_by": report.resolved_by,
        "resolved_at": report.resolved_at,
        "reporter_id": report.reporter_id,
        "reporter_name": report.reporter.name if report.reporter else None,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "target": targets.get(
            (report.target_type, report.target_id),
            _deleted_target(report.target_type, report.target_id),
        ),
    }


def _reasons(raw: str | None) -> tuple[list[str], str | None]:
    """flag_reasons sütununu (kodlar, Türkçe açıklama) çiftine çevirir."""
    codes = moderation.split_reasons(raw)
    return codes, (moderation.describe(codes) if codes else None)


# ---------------------------------------------------------------------------
# özet
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=SummaryOut)
def admin_summary(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Yönetici panosunun üst kartları."""
    return {
        "open_reports": _count(
            db, select(models.Report.id).where(models.Report.resolved.is_(False))
        ),
        "flagged_listings": _count(
            db, select(models.Listing.id).where(models.Listing.is_flagged.is_(True))
        ),
        "flagged_messages": _count(
            db, select(models.Message.id).where(models.Message.is_flagged.is_(True))
        ),
        "suspended_users": _count(
            db, select(models.User.id).where(models.User.is_suspended.is_(True))
        ),
        "total_users": _count(db, select(models.User.id)),
        "active_listings": _count(
            db, select(models.Listing.id).where(models.Listing.is_active.is_(True))
        ),
    }


# ---------------------------------------------------------------------------
# bildirim (rapor) kuyruğu
# ---------------------------------------------------------------------------

@router.get("/reports", response_model=list[AdminReportOut])
def admin_reports(
    status: Literal["open", "resolved", "all"] = Query("open"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """İnceleme kuyruğu: her satır karar vermeye yetecek bağlamı taşır."""
    stmt = (
        select(models.Report)
        .options(selectinload(models.Report.reporter))
        .order_by(models.Report.created_at.desc(), models.Report.id.desc())
    )
    if status == "open":
        stmt = stmt.where(models.Report.resolved.is_(False))
    elif status == "resolved":
        stmt = stmt.where(models.Report.resolved.is_(True))

    rows = list(db.scalars(stmt.limit(limit)).all())
    targets = _load_targets(db, rows)
    return [_report_row(row, targets) for row in rows]


@router.patch("/reports/{report_id}", response_model=AdminReportOut)
def resolve_report(
    report_id: int,
    payload: ReportResolveIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Raporu kapatır ya da yeniden açar; kararı kimin verdiğini kaydeder."""
    row = db.get(models.Report, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rapor bulunamadı.")

    row.resolved = payload.resolved
    if payload.resolved:
        if payload.resolution_note is not None:
            row.resolution_note = payload.resolution_note.strip() or None
        row.resolved_by = admin.id
        row.resolved_at = _utcnow()
    else:
        # Yeniden açılan rapor kapatma kararının HİÇBİR izini taşımamalı:
        # kim/ne zaman ile birlikte karar notu da silinir. (Eskiden not
        # kalıyordu; istemci yeniden açarken not alanını hiç göndermediği
        # için bildirim, geri alınmış bir kararın notuyla kuyruğa dönüyordu.)
        row.resolution_note = None
        row.resolved_by = None
        row.resolved_at = None

    db.commit()
    db.refresh(row)
    return _report_row(row, _load_targets(db, [row]))


# ---------------------------------------------------------------------------
# işaretlenen içerik kuyruğu
# ---------------------------------------------------------------------------

@router.get("/flagged", response_model=list[FlaggedOut])
def admin_flagged(
    kind: Literal["listing", "message", "all"] = Query("all"),
    status: Literal["pending", "removed"] = Query(
        "pending",
        description=(
            "pending: incelenmemiş işaretler (is_flagged), "
            "removed: yönetici kaldırdı — geri alınabilir"
        ),
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """İnceleme kuyrukları.

    status=pending (varsayılan): otomatik denetimin işaretlediği, henüz
    incelenmemiş içerik. İnceleme (clear/remove) is_flagged'ı False yaptığı
    için incelenmiş kayıtlar bu kuyruktan kendiliğinden düşer.

    status=removed: yöneticinin kaldırdığı içerik. Bu kuyruk olmadan
    kaldırılan kayıt hiçbir yerde görünmüyordu; görünmeyeni geri almak da
    mümkün değildi. Geri alma: POST /api/admin/{kind}/{id}/restore.
    """
    removed_only = status == "removed"
    rows: list[dict] = []

    if kind in ("listing", "all"):
        listing_filter = (
            models.Listing.moderation_removed.is_(True)
            if removed_only
            else models.Listing.is_flagged.is_(True)
        )
        listings = db.scalars(
            select(models.Listing)
            .options(selectinload(models.Listing.owner))
            .where(listing_filter)
            .order_by(models.Listing.created_at.desc(), models.Listing.id.desc())
            .limit(limit)
        ).all()
        for row in listings:
            codes, text = _reasons(row.flag_reasons)
            rows.append(
                {
                    "kind": "listing",
                    "id": row.id,
                    "title": row.title,
                    "content": row.description,
                    "district": row.district,
                    "author_id": row.owner_id,
                    "author_name": row.owner.name if row.owner else None,
                    "match_id": None,
                    "is_active": bool(row.is_active),
                    "moderation_removed": bool(row.moderation_removed),
                    "active_before_removal": (
                        None
                        if row.active_before_removal is None
                        else bool(row.active_before_removal)
                    ),
                    "flag_reasons": codes,
                    "flag_reasons_text": text,
                    "reviewed_by": row.reviewed_by,
                    "reviewed_at": row.reviewed_at,
                    "review_note": row.review_note,
                    "created_at": row.created_at,
                }
            )

    if kind in ("message", "all"):
        message_filter = (
            models.Message.moderation_removed.is_(True)
            if removed_only
            else models.Message.is_flagged.is_(True)
        )
        messages = db.scalars(
            select(models.Message)
            .options(selectinload(models.Message.sender))
            .where(message_filter)
            .order_by(models.Message.created_at.desc(), models.Message.id.desc())
            .limit(limit)
        ).all()
        for row in messages:
            codes, text = _reasons(row.flag_reasons)
            rows.append(
                {
                    "kind": "message",
                    "id": row.id,
                    "title": None,
                    # Kaldırılmış mesajda content zaten REMOVED_CONTENT sabiti;
                    # kararı gözden geçirmek için asıl metin gerekiyor.
                    "content": crypto.decrypt(row.original_content or row.content)
                    or "",
                    "district": None,
                    "author_id": row.sender_id,
                    "author_name": row.sender.name if row.sender else None,
                    "match_id": row.match_id,
                    "is_active": None,
                    "moderation_removed": bool(row.moderation_removed),
                    "active_before_removal": None,  # ilana özgü alan
                    "flag_reasons": codes,
                    "flag_reasons_text": text,
                    "reviewed_by": row.reviewed_by,
                    "reviewed_at": row.reviewed_at,
                    "review_note": row.review_note,
                    "created_at": row.created_at,
                }
            )

    # İki kuyruk birleştiğinde de "en yeni önce" korunur.
    rows.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    return rows[:limit]


@router.post("/flagged/{kind}/{item_id}/review", response_model=ReviewOut)
def review_flagged(
    kind: FlagKind,
    item_id: int,
    payload: ReviewIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """İşareti temizler ("clear") ya da içeriği yayından kaldırır ("remove").

    Hiçbir satır silinmez ve hiçbir metin kaybolmaz: ilan pasife çekilir,
    mesajın metni original_content'e TAŞINIR ve yerine REMOVED_CONTENT sabiti
    yazılır. İki karar da POST /api/admin/{kind}/{id}/restore ile geri alınır;
    kaldırılan kayıt GET /flagged?status=removed kuyruğunda bulunur.

    "clear" İŞARETİ temizler, KALDIRMAYI DEĞİL. İçeriğe dokunmaz ama nötr de
    değildir: is_flagged, reviewed_by, reviewed_at ve review_note yazılır
    (karar kaydı tutulur).

    Zaten kaldırılmış bir kayda "clear" 400 ile reddedilir. Eskiden kabul
    ediliyordu ve tutarsız bir durum üretiyordu: moderation_removed True
    kalırken yanıt content_removed:False dönüyor, üstelik kaldırma kararının
    reviewed_by/reviewed_at izi de üzerine yazılıyordu. Kaldırmayı geri
    almanın tek yolu POST /api/admin/{kind}/{id}/restore'dur.
    """
    model = models.Listing if kind == "listing" else models.Message
    row = db.get(model, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı.")
    if payload.action == "clear" and row.moderation_removed:
        raise HTTPException(
            status_code=400,
            detail=(
                "Bu içerik yönetici tarafından kaldırılmış; işaret temizlemek "
                "kaldırmayı geri almaz. Geri almak için 'restore' kullan."
            ),
        )

    note = payload.note.strip() if payload.note else None
    content_removed = False

    if payload.action == "remove":
        if kind == "listing":
            # Kaldırmadan ÖNCEKİ yayın durumunu sakla; geri alma buraya döner.
            # İkinci kez "remove" gelirse (çift tıklama) ilk kaydı EZMEMEK
            # için bayrak kontrolü şart — yoksa ikinci çağrı "kaldırmadan önce
            # de kapalıydı" yazar ve geri alma ilanı yayına getiremezdi.
            if not row.moderation_removed:
                row.active_before_removal = bool(row.is_active)
            row.is_active = False
        elif not row.moderation_removed:
            # İkinci kez "remove" gelirse (çift tıklama) sabit metnin
            # original_content'i EZMEMESİ için bayrak kontrolü şart.
            row.original_content = row.content
            # Sabit şifrelenmeden yazılır: crypto.decrypt "enc:v1:" ile
            # başlamayan değeri olduğu gibi döndürür, istemciye bozulmadan
            # ulaşır.
            row.content = REMOVED_CONTENT
        row.moderation_removed = True
        content_removed = kind == "message"

    # "clear" da "remove" da incelemeyi bitirir; kayıt işaretli kuyruktan düşer.
    row.is_flagged = False
    row.reviewed_by = admin.id
    row.reviewed_at = _utcnow()
    row.review_note = note
    db.commit()
    db.refresh(row)

    return {
        "kind": kind,
        "id": row.id,
        "action": payload.action,
        "is_flagged": bool(row.is_flagged),
        "is_active": bool(row.is_active) if kind == "listing" else None,
        "moderation_removed": bool(row.moderation_removed),
        "content_removed": content_removed,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
    }


@router.post("/{kind}/{item_id}/restore", response_model=RestoreOut)
def restore_removed(
    kind: FlagKind,
    item_id: int,
    payload: RestoreIn | None = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Yöneticinin kaldırdığı içeriği KALDIRMADAN ÖNCEKİ hâline geri alır.

    - ilan  : is_active = active_before_removal, moderation_removed False
    - mesaj : content = original_content, original_content NULL,
              moderation_removed False

    "Yayına al" değil "kaldırmayı geri al": kullanıcının kendi kararı iki
    yerden korunur.
      1. Sahibinin kendi kapattığı ilan (is_active False ama
         moderation_removed False) buradan hiç açılmaz — 400 döner.
      2. Sahibi zaten kapatmışken yönetici kuyruktan "kaldır" demişse
         (işaretli kayıt kapatılınca da kuyrukta kaldığı için olabilir)
         geri alma ilanı yayına SOKMAZ, kapalı bırakır. Yanıttaki is_active
         gerçeği söyler; arayüz "yeniden yayında" demeden önce onu okur.

    METNİ KURTARILAMAYAN MESAJ (original_content NULL — bu sütunlar
    eklenmeden önce kaldırılmış eski kayıt) HİÇ DEĞİŞTİRİLMEZ:
    `restored:false, content_recoverable:false` döner ve moderation_removed
    True kalır. Eskiden bu durumda metin geri konmadan bayrak indiriliyordu;
    sonuç, kaydın Kaldırılanlar kuyruğundan düşmesi, kullanıcının hâlâ
    "kaldırıldı" görmesi, ikinci restore'un 400 vermesi ve kaydın hiçbir
    uçtan bulunamaz hâle gelmesiydi — modülün 1. ilkesinin ("kaldırılan
    içerik BULUNABİLİR kalır") tam tersi.
    """
    model = models.Listing if kind == "listing" else models.Message
    row = db.get(model, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İçerik bulunamadı.")
    if not row.moderation_removed:
        raise HTTPException(
            status_code=400,
            detail="Bu içerik yönetici tarafından kaldırılmamış; zaten yayında.",
        )

    if kind == "message" and row.original_content is None:
        # Geri alacak bir şey yok. Kaydı OLDUĞU GİBİ bırakıyoruz: bayrağı
        # indirmek kaydı kuyruktan düşürür ve bir daha bulunamaz hâle
        # getirirdi. reviewed_* alanlarına da dokunmuyoruz — kaldırma
        # kararının izi, gerçekleşmemiş bir geri almayla silinmemeli.
        return {
            "kind": kind,
            "id": row.id,
            "restored": False,
            "is_active": None,
            "moderation_removed": True,
            "content_recoverable": False,
            "content_restored": False,
            "reviewed_by": row.reviewed_by,
            "reviewed_at": row.reviewed_at,
            "review_note": row.review_note,
        }

    note = (payload.note.strip() if payload and payload.note else None) or None
    content_restored: bool | None = None
    content_recoverable: bool | None = None

    if kind == "listing":
        # Kaldırmadan önceki hâle DÖN, koşulsuz yayına alma.
        # Sahibi ilanı zaten kapatmışken yönetici kuyruktan "kaldır" derse
        # (işaretli kayıt kapatılınca da kuyrukta kalır) geri alma o ilanı
        # sahibinin haberi olmadan yeniden yayına sokuyordu. Artık sokmaz.
        # NULL = sütun eklenmeden önce kaldırılmış kayıt; önceki durum
        # bilinmediği için eski davranış (yayına al) korunur.
        row.is_active = (
            True if row.active_before_removal is None
            else bool(row.active_before_removal)
        )
        row.active_before_removal = None
    else:
        # Metin saklanmış: yerine geri konur. Ama "geri kondu" ile
        # "OKUNABİLİR" aynı şey değil — anahtar kaybolmuş ya da dönmüşse
        # çözülen değer crypto.UNREADABLE olur ve kullanıcı hâlâ metni
        # göremez. content_restored bu ayrımı yapar; arayüz "Mesajın metni
        # geri kondu." derken yalan söylemesin.
        content_recoverable = True
        row.content = row.original_content
        row.original_content = None
        content_restored = crypto.decrypt(row.content) not in (
            None,
            crypto.UNREADABLE,
        )

    row.moderation_removed = False
    row.reviewed_by = admin.id
    row.reviewed_at = _utcnow()
    row.review_note = note
    db.commit()
    db.refresh(row)

    return {
        "kind": kind,
        "id": row.id,
        "restored": True,
        "is_active": bool(row.is_active) if kind == "listing" else None,
        "moderation_removed": bool(row.moderation_removed),
        "content_recoverable": content_recoverable,
        "content_restored": content_restored,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
    }


# ---------------------------------------------------------------------------
# kullanıcı askıya alma
# ---------------------------------------------------------------------------

def _admin_user_row(row: models.User) -> dict:
    """Yöneticiye dönen kullanıcı satırı — e-posta yalnız askıdakilerde.

    Askıyı kaldırırken doğru hesaba baktığını doğrulamak için e-posta
    gerekiyor; aktif kullanıcıların adresi hiçbir yönetici ekranında
    kullanılmıyor, o yüzden hiç dönmüyor (bkz. modül başındaki ilke 3).
    """
    return {
        "id": row.id,
        "email": row.email if row.is_suspended else None,
        "name": row.name,
        "university": row.university,
        "is_admin": row.is_admin,
        "is_suspended": bool(row.is_suspended),
        "suspended_at": row.suspended_at,
        "suspended_reason": row.suspended_reason,
        "suspended_by": row.suspended_by,
        "unsuspended_at": row.unsuspended_at,
        "unsuspended_by": row.unsuspended_by,
        "last_suspension_reason": row.last_suspension_reason,
        "created_at": row.created_at,
    }


@router.get("/users", response_model=list[AdminUserOut])
def admin_users(
    suspended: bool = Query(
        ...,
        description=(
            "ZORUNLU. true: askıdakiler, false: aktifler. Filtresiz çağrı "
            "yok: tüm kullanıcı tabanını dökmek hiçbir karar için gerekmiyor."
        ),
    ),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Kullanıcı listesi — "Askıdakiler" sekmesi suspended=true ile çeker."""
    if suspended:
        # Askıdakiler en son askıya alınan başta görünsün.
        stmt = (
            select(models.User)
            .where(models.User.is_suspended.is_(True))
            .order_by(models.User.suspended_at.desc(), models.User.id.desc())
        )
    else:
        stmt = (
            select(models.User)
            .where(models.User.is_suspended.is_(False))
            .order_by(models.User.id.desc())
        )
    return [_admin_user_row(row) for row in db.scalars(stmt.limit(limit)).all()]


@router.post("/users/{user_id}/suspend", response_model=AdminUserOut)
def suspend_user(
    user_id: int,
    payload: SuspendIn | None = None,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Kullanıcıyı askıya alır: giriş kapanır, oturumları düşer, ilanları gizlenir.

    is_active'e DOKUNULMAZ — askı kalkınca ilanlar aynen geri gelir.
    """
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    # Sıra önemli: yönetici kendisi de yönetici olduğu için önce "kendini"
    # kontrolü gelmeli, yoksa 400 yerine 403 dönerdi.
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="Kendini askıya alamazsın.")
    if target.is_admin:
        raise HTTPException(
            status_code=403, detail="Başka bir yöneticiyi askıya alamazsın."
        )

    target.is_suspended = True
    target.suspended_at = _utcnow()
    reason = payload.reason if payload else None
    target.suspended_reason = (reason or "").strip() or None
    target.suspended_by = admin.id
    # Yeni askı, önceki askının "kaldırıldı" izini geçersiz kılar; yürürlükteki
    # durumla geçmiş karışmasın diye temizlenir (gerekçe geçmişi
    # last_suspension_reason'da durmaya devam eder).
    target.unsuspended_at = None
    target.unsuspended_by = None
    # Mevcut oturumlar düşmezse askı yalnızca yeni girişleri engellerdi.
    db.query(models.AuthToken).filter(
        models.AuthToken.user_id == target.id
    ).delete(synchronize_session=False)
    db.commit()
    db.refresh(target)
    return _admin_user_row(target)


@router.post("/users/{user_id}/unsuspend", response_model=AdminUserOut)
def unsuspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Askıyı kaldırır; kullanıcı ve ilanları eski hâline döner.

    GERİ ALMA DA BİR EYLEMDİR, KAYDEDİLİR (bkz. modül başındaki ilke 4).
    Eskiden bu uç suspended_* alanlarını NULL'a çekiyordu ve geriye hiçbir iz
    kalmıyordu: hesabın daha önce askıya alınıp alınmadığı, gerekçesinin ne
    olduğu ve askıyı kimin kaldırdığı hiçbir yerden okunamıyordu. Artık
    gerekçe SİLİNMEZ, last_suspension_reason'a taşınır; kaldıran yönetici ve
    zamanı ayrıca yazılır.
    """
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    if target.is_suspended:
        # Gerekçe geçmişe taşınır. Yürürlükteki alanda bırakılsaydı arayüz
        # aktif bir hesapta yürürlükte olmayan bir gerekçe gösterirdi.
        target.last_suspension_reason = target.suspended_reason
        target.unsuspended_at = _utcnow()
        target.unsuspended_by = admin.id

    target.is_suspended = False
    target.suspended_at = None
    target.suspended_reason = None
    target.suspended_by = None
    db.commit()
    db.refresh(target)
    # Askı kalktığı an e-posta da dönmez: artık gösterilecek bir gerekçe yok.
    return _admin_user_row(target)
