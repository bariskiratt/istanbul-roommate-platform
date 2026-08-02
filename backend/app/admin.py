"""Yönetici (moderasyon) uçları — /api/admin/*.

Tasarım ilkeleri:

1. ÖNCE GERİ ALINABİLİR YOL. Bir işin geri alınabilir bir karşılığı varsa
   yıkıcı olan değil o kullanılır:
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

1b. YIKICI YOL DA VAR, AMA AYRI VE İZLİ. Kaldırma her derde deva değil:
   satırın gerçekten gitmesi gereken durumlar (hukuki talep, gerçek kişi
   verisi, tekrar tekrar açılan sahte hesap) elde yalnızca "gizle" varken
   çözülemiyordu. İki uç kalıcı siler:
     DELETE /listings/{id}   ilan satırı gider
     DELETE /users/{id}      hesap ve bağlı verisi gider
   Bu ikisinin üç ortak kuralı var:
     - GEREKÇE ZORUNLU (gövdede reason),
     - models.AdminAction'a denetim kaydı yazılır (GET /actions),
     - bağlı kayıtlar temizlenir ama SOHBET YAŞAR: ilan silinince
       matches.listing_id NULL'a çekilir, eşleşme ve mesajlar durur.
       İnsanların birbirine yazdıkları, konuştukları ilan silindi diye
       silinmez.
   Geri alınabilir eylemler AdminAction'a YAZILMAZ; onlar izini kendi
   sütunlarında (reviewed_by, suspended_by, resolved_by) zaten bırakıyor ve
   aynı olayı iki yerde tutmak ikisinin çelişmesi demektir.
2. BİLDİRENİN KİMLİĞİ BİLDİRİLENE GÖSTERİLMEZ. Bu uçlar yalnızca yöneticiye
   açıktır; raporun reporter bilgisi buradan dışarı sızmaz.
3. YÖNETİCİ YALNIZCA KARAR İÇİN GEREKENİ GÖRÜR. Raporlanan mesajın metni
   döner, sohbetin tamamı DÖNMEZ. Kullanıcı listesi e-postayı yalnız askıdaki
   hesaplar için döner ve sayfalıdır (bir istekte tüm taban dökülmez).
   E-posta ARAMADA kullanılabilir (?q=) ama yanıtta yine dönmez: yöneticinin
   "şu adresi bul" ihtiyacı, tüm adresleri görmesini gerektirmiyor.

3b. KİMLİĞE BÜRÜNME YOK. "Bu kullanıcı olarak giriş yap" diye bir uç bilerek
   eklenmedi ve eklenmemeli. Yönetici bildirilen/işaretlenen içeriği zaten
   görebiliyor; birinin oturumunu devralıp özel sohbetlerini okumak veya onun
   adına mesaj yazmak bambaşka bir yetkidir. İhtiyaç doğarsa doğru cevap
   salt-okunur bir görüntüleyicidir, oturum devralma değil.
4. HER EYLEM KAYDEDİLİR: resolved_by/resolved_at, reviewed_by/reviewed_at,
   suspended_by/suspended_at. Geri alma da bir eylemdir: ilan/mesaj geri
   alınırken review_note'a not yazılır, askı kaldırılırken
   unsuspended_by/unsuspended_at yazılır ve gerekçe silinmeyip
   last_suspension_reason'a taşınır.

Tüm uçlar require_admin ile korunur: girişsiz 401, admin olmayan 403.
"""

import json
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import crypto, models, moderation
from app.auth import purge_user
from app.db import get_db
from app.listings import (
    FEATURE_FIELDS,
    ListingOut,
    ListingUpdate,
    flag_state,
    moderate_listing_text,
    purge_listing,
)
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


class AdminListingOut(ListingOut):
    """İlan satırının yönetici sürümü — moderasyon alanları da görünür.

    ListingOut'tan türer: yönetici düzenleme formu normal ilanın TÜM
    alanlarını göstermek zorunda, o listeyi ikinci kez yazmak ikisinin
    zamanla ayrışması demekti.

    `type` bilerek Literal'den str'ye gevşetildi: yönetici listesi BOZUK
    kayıtları da göstermek zorunda. Literal kalsaydı tipi tanınmayan tek bir
    satır tüm listeyi 500'e düşürür, yani yöneticinin düzeltmesi gereken kayıt
    tam da onu göremediği kayıt olurdu.
    """

    type: str
    # Ev ilanı özellikleri ListingOut'ta zaten var; buraya yalnız yönetici
    # alanları ekleniyor.
    moderation_removed: bool
    active_before_removal: bool | None
    is_flagged: bool
    flag_reasons: list[str]
    flag_reasons_text: str | None
    # Sahibi askıdaysa ilan hiçbir genel listede görünmez. Yayına alma ucu
    # bunu ENGELLEMEZ ama arayüz "yayında" derken bu alanı okumalı: askıdaki
    # sahibin ilanı is_active=True olsa da kimseye görünmez.
    owner_suspended: bool
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_note: str | None


class ListingPublishOut(BaseModel):
    """Yayına alma sonucu."""

    id: int
    is_active: bool
    # Bu çağrı gerçekten bir şey değiştirdi mi. İlan zaten yayındaysa uç
    # başarılı döner ama False yazar; arayüz "yayına alındı" demeden önce
    # buna bakar.
    changed: bool
    moderation_removed: bool
    owner_suspended: bool


class DeleteIn(BaseModel):
    """Kalıcı silme gövdesi. GEREKÇE ZORUNLU.

    Sebep: bu iki uç geri alınamaz. Denetim kaydına yazılacak tek açıklama
    burası; boş bırakılabilseydi kayıt "birisi bir şeyi sildi"den ibaret
    kalır, tutmanın anlamı kalmazdı.
    """

    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        # min_length boşluklardan oluşan bir gerekçeyi geçirirdi.
        if not v.strip():
            raise ValueError("Silme gerekçesi boş olamaz.")
        return v.strip()


class AdminDeleteOut(BaseModel):
    """Kalıcı silme sonucu."""

    kind: Literal["listing", "user"]
    id: int
    deleted: bool
    # Yazılan denetim kaydının id'si (GET /api/admin/actions ile bulunur).
    action_id: int
    # Birlikte temizlenen bağlı kayıt sayıları. "İlanı sildim, sohbetlere ne
    # oldu" sorusunun cevabı: detached_matches, listing_id'si NULL'a çekilip
    # YAŞAMAYA DEVAM EDEN eşleşme sayısıdır — silinen değil.
    cleanup: dict[str, int]


class AdminActionOut(BaseModel):
    id: int
    # NULL = eylemi yapan yönetici o zamandan beri hesabını sildi. Kayıt
    # aktörünü kaybeder ama kaybolmaz.
    actor_id: int | None
    actor_name: str | None
    action: str
    target_type: str
    target_id: int
    reason: str | None
    detail: str | None
    created_at: datetime


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


def _record_action(
    db: Session,
    admin: models.User,
    action: str,
    target_type: str,
    target_id: int,
    *,
    reason: str | None = None,
    detail: dict | None = None,
) -> models.AdminAction:
    """Denetim kaydı yazar (commit ETMEZ — çağıran eylemle aynı işlemde).

    Aynı işlemde olması şart: kayıt ayrı commit edilseydi eylem başarısız
    olduğunda "sildim" diyen ama hiçbir şey silmemiş bir kayıt kalırdı.
    """
    row = models.AdminAction(
        actor_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        # ensure_ascii=False: Türkçe metin kayıtta okunabilir kalsın.
        detail=json.dumps(detail, ensure_ascii=False, default=str)
        if detail
        else None,
    )
    db.add(row)
    db.flush()
    return row


def _search_pattern(raw: str) -> str:
    """Kısmi arama deseni. LIKE joker karakterleri kaçırılır.

    Kaçırma olmadan "%" yazan bir arama tüm tabloyu, "_" ise rastgele
    satırları getirirdi — yönetici aradığını bulduğunu sanırdı.
    Harf duyarsızlık `ilike` ile sağlanır (bkz. _ilike).
    """
    escaped = raw.strip().replace("\\", r"\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


def _ilike(column, pattern: str):
    """Harf duyarsız kısmi eşleşme.

    ilike kullanılıyor çünkü iki tarafa da AYNI dönüşümü uyguluyor: Postgres'te
    gerçek ILIKE, SQLite'ta `lower(sütun) LIKE lower(desen)`. Elle
    `func.lower(col).like(q.lower())` yazsaydık Python'un ve veritabanının
    küçük harf kuralları Türkçe harflerde ayrışırdı (Python "İ".lower() ucuna
    birleşen nokta ekler, SQLite hiç dokunmaz) ve arama sessizce boş dönerdi.

    NOT: SQLite yalnızca ASCII harflerde duyarsızdır; "AYŞE" araması
    "Ayşe"yi orada bulmaz (Postgres'te bulur). Yerel geliştirmeye özgü bir
    kısıt olduğu için ayrıca bir çözüm eklenmedi.
    """
    return column.ilike(pattern, escape="\\")


# Yönetici ilan satırında olduğu gibi taşınan alanlar (ListingOut ile aynı).
_LISTING_FIELDS: tuple[str, ...] = (
    "id",
    "type",
    "title",
    "description",
    "district",
    "neighborhood",
    "photos",
    "rent",
    "room_count",
    "smoking_allowed",
    "pets_allowed",
    *FEATURE_FIELDS,
    "budget_min",
    "budget_max",
    "is_active",
    "created_at",
)


def _admin_listing_row(row: models.Listing) -> dict:
    """İlanın yönetici görünümü — moderasyon durumu dahil."""
    codes, text = _reasons(row.flag_reasons)
    data = {name: getattr(row, name) for name in _LISTING_FIELDS}
    data["photos"] = row.photos or []
    return data | {
        "owner_id": row.owner_id,
        "owner_name": row.owner.name if row.owner else None,
        "owner_university": row.owner.university if row.owner else None,
        "owner_suspended": bool(row.owner.is_suspended) if row.owner else False,
        "moderation_removed": bool(row.moderation_removed),
        "active_before_removal": (
            None
            if row.active_before_removal is None
            else bool(row.active_before_removal)
        ),
        "is_flagged": bool(row.is_flagged),
        "flag_reasons": codes,
        "flag_reasons_text": text,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "review_note": row.review_note,
    }


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
# ilan yönetimi — arama, düzenleme, yayına alma, KALICI SİLME
# ---------------------------------------------------------------------------

@router.get("/listings", response_model=list[AdminListingOut])
def admin_listings(
    q: str | None = Query(
        None,
        max_length=80,
        description="Başlık, ilçe ya da sahip (ad/e-posta) içinde kısmi arama",
    ),
    status: Literal["all", "active", "inactive", "removed", "flagged"] = Query(
        "all",
        description=(
            "all: hepsi, active: yayında, inactive: SAHİBİNİN kapattığı, "
            "removed: YÖNETİCİNİN kaldırdığı, flagged: incelenmemiş işaretli"
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """TÜM ilanlar — pasifler ve yöneticinin kaldırdıkları dâhil.

    NEDEN AYRI BİR UÇ: /api/listings tasarımı gereği yalnız yayındaki ve
    sahibi askıda OLMAYAN ilanları döner. Yönetici tam da o filtrenin
    gizlediklerine bakmak zorunda; oradan bakıldığında "sahibi askıya alınmış
    ilan" ya da "kapatılmış ilan" hiç yokmuş gibi görünüyordu.

    `status=inactive` ile `status=removed` ayrımı önemli: ikisinde de
    is_active False'tur ama ilki SAHİBİNİN kararı, ikincisi YÖNETİCİNİN.
    Yayına alma ucu yalnız ilkine dokunur (bkz. publish_listing).

    E-posta arama koşulunda kullanılır ama yanıtta DÖNMEZ (bkz. ilke 3).
    """
    stmt = (
        select(models.Listing)
        .options(selectinload(models.Listing.owner))
        .order_by(models.Listing.created_at.desc(), models.Listing.id.desc())
    )

    if status == "active":
        stmt = stmt.where(models.Listing.is_active.is_(True))
    elif status == "inactive":
        # Sahibinin kapattığı: pasif AMA yönetici kaldırması değil.
        stmt = stmt.where(
            models.Listing.is_active.is_(False),
            models.Listing.moderation_removed.is_(False),
        )
    elif status == "removed":
        stmt = stmt.where(models.Listing.moderation_removed.is_(True))
    elif status == "flagged":
        stmt = stmt.where(models.Listing.is_flagged.is_(True))

    if q and q.strip():
        pattern = _search_pattern(q)
        owners = select(models.User.id).where(
            _ilike(models.User.name, pattern) | _ilike(models.User.email, pattern)
        )
        stmt = stmt.where(
            _ilike(models.Listing.title, pattern)
            | _ilike(models.Listing.district, pattern)
            | models.Listing.owner_id.in_(owners)
        )

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [_admin_listing_row(row) for row in rows]


@router.patch("/listings/{listing_id}", response_model=AdminListingOut)
def admin_update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Herhangi bir ilanı düzenler — sahiplik şartı YOK.

    PATCH /api/listings/{id} sahibinden başkasına 403 verir ve pasif ilanı hiç
    bulmaz; yönetici için bu, "ya tamamen kaldır ya hiç dokunma" demekti.
    Oysa sorunların çoğu tek bir satır metin düzeltmesiyle çözülüyor:
    açıklamadaki telefon numarasını silmek, yanlış ilçeyi düzeltmek.

    İÇERİK DENETİMİ ÇALIŞIR AMA ENGELLEMEZ. Kullanıcı yolunda "block" sonucu
    422'dir; burada 422 atmak, düzeltmeye gelen yöneticiyi düzeltmek istediği
    metnin kendisi yüzünden dışarıda bırakırdı. Sonuç kayda İŞARET olarak
    yazılır (is_flagged / flag_reasons), yani yöneticinin bıraktığı metin de
    inceleme kuyruğunda görünür — denetimden muaf değil, sadece engellenmiyor.

    reviewed_by / reviewed_at'e DOKUNULMAZ: onlar "kaldır/temizle" kararının
    izidir, düzenleme o karar değildir. moderation_removed de değişmez —
    kaldırılmış bir ilanın metni düzeltilebilir, ama kaldırılmış kalır.
    """
    row = db.get(models.Listing, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")

    # null gönderilen alanlar "değiştirme" sayılır — sahibin ucundaki kuralın
    # aynısı: zorunlu alanlar PATCH ile boşaltılıp kayıt bozulmasın.
    updates = {
        k: v
        for k, v in payload.model_dump(exclude_unset=True).items()
        if v is not None
    }
    eff_min = updates.get("budget_min", row.budget_min)
    eff_max = updates.get("budget_max", row.budget_max)
    if eff_min is not None and eff_max is not None and eff_min > eff_max:
        raise HTTPException(
            status_code=422, detail="Bütçe alt sınırı üst sınırdan büyük olamaz."
        )

    changed = {k: v for k, v in updates.items() if getattr(row, k) != v}
    if not changed:
        # Değişen bir şey yok: denetim kaydını gereksiz yere şişirmeyelim.
        return _admin_listing_row(row)

    new_title = changed.get("title", row.title)
    new_description = changed.get("description", row.description)
    before = {"title": row.title, "description": row.description}
    if "title" in changed or "description" in changed:
        result = moderate_listing_text(new_title, new_description)
        # "block" da "flag" da işaret demektir: yönetici engellenmez ama
        # yazdığı metin denetimden muaf değildir (bkz. listings.flag_state).
        row.is_flagged, row.flag_reasons = flag_state(result)

    for key, value in changed.items():
        setattr(row, key, value)

    # Düzenleme "geri alınabilir" görünür ama ÖNCEKİ METİN YOK OLUR; sahibinin
    # ne yazdığı yalnızca burada kalır.
    detail = {"fields": sorted(changed)}
    if "title" in changed or "description" in changed:
        detail["before"] = before
    _record_action(
        db, admin, "listing_update", "listing", row.id, detail=detail
    )
    db.commit()
    db.refresh(row)
    return _admin_listing_row(row)


@router.post("/listings/{listing_id}/publish", response_model=ListingPublishOut)
def publish_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """İlanı yayına alır (is_active=True).

    Bu uç, SAHİBİNİN kendi kapattığı ilan için var. Kapatma kullanıcı
    açısından tek yönlüydü (bkz. listings.deactivate_listing): yanlışlıkla
    kapatan biri destek isteyince yapılabilecek hiçbir şey yoktu.

    YÖNETİCİNİN KALDIRDIĞI İLANA DOKUNMAZ — 409 döner. Sebebi yetki değil,
    tek yazarlık: moderation_removed=True olan kaydın is_active'i
    active_before_removal'a göre geri alınır ve o iş POST
    /api/admin/listing/{id}/restore'a aittir. İki ucun aynı alanı iki farklı
    kuralla yazması, üçüncü bir durumda hangisinin kazandığını kimsenin
    bilemediği bir hataya dönüşür.
    """
    row = db.get(models.Listing, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.moderation_removed:
        raise HTTPException(
            status_code=409,
            detail=(
                "Bu ilan yönetici tarafından kaldırılmış. Yayına almak için "
                "POST /api/admin/listing/{id}/restore kullan."
            ),
        )

    changed = not row.is_active
    if changed:
        row.is_active = True
        _record_action(db, admin, "listing_publish", "listing", row.id)
        db.commit()
        db.refresh(row)

    return {
        "id": row.id,
        "is_active": bool(row.is_active),
        "changed": changed,
        "moderation_removed": bool(row.moderation_removed),
        # Sahibi askıdaysa ilan yayında SAYILIR ama kimseye görünmez; arayüz
        # "yayına alındı" derken bunu da söylemeli.
        "owner_suspended": bool(row.owner.is_suspended) if row.owner else False,
    }


@router.delete("/listings/{listing_id}", response_model=AdminDeleteOut)
def delete_listing(
    listing_id: int,
    payload: DeleteIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """İlanı KALICI siler — satır gider, geri alınamaz.

    ÖNCE "kaldır"ı düşün (POST /flagged/listing/{id}/review, action=remove):
    o karar geri alınabilir ve satır durur. Bu uç, satırın gerçekten gitmesi
    gereken durumlar için: hukuki kaldırma talebi, üçüncü kişinin izinsiz
    paylaşılan adresi/fotoğrafı gibi "gizlemek yetmez" halleri.

    SOHBET YAŞAR. İlana bağlı eşleşmelerin listing_id'si NULL'a çekilir,
    eşleşme ve mesajlar durur (bkz. listings.purge_listing). İlan bir
    tanışmanın sebebiydi; sebebi silmek konuşmayı silmez.

    Gerekçe zorunlu ve models.AdminAction'a yazılır: silinen satır geri
    gelmeyeceği için "neyi neden sildim" sorusunun cevabı başka hiçbir yerde
    kalmıyor.
    """
    row = db.get(models.Listing, listing_id)
    if row is None:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")

    # Satır silinmeden ÖNCE okunmalı: sonrasında okunacak bir yer kalmıyor.
    detail = {
        "title": row.title,
        "district": row.district,
        "type": row.type,
        "owner_id": row.owner_id,
        "owner_name": row.owner.name if row.owner else None,
        "created_at": row.created_at,
    }
    cleanup = purge_listing(db, row)
    action = _record_action(
        db,
        admin,
        "listing_delete",
        "listing",
        listing_id,
        reason=payload.reason,
        detail=detail,
    )
    db.commit()
    return {
        "kind": "listing",
        "id": listing_id,
        "deleted": True,
        "action_id": action.id,
        "cleanup": cleanup,
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


def _protect_admin_accounts(
    target: models.User, admin: models.User, verb: str
) -> None:
    """Yönetici KENDİNE ya da BAŞKA BİR YÖNETİCİYE bu işlemi uygulayamaz.

    BU BİR YETKİ KISITI DEĞİL, EMNİYET KİLİDİDİR. Askıya alma ve kalıcı silme
    yöneticinin kendi erişimini de kesen işlemler: son yönetici kendini askıya
    alır ya da silerse platformun yönetimi GERİ DÖNÜLEMEZ biçimde kaybolur —
    askıyı kaldıracak, hesabı geri getirecek bir uç yok, çünkü o uçlara
    girebilecek kimse kalmıyor. Aynı gerekçe yöneticiler arasında da geçerli:
    iki yönetici birbirini silebilseydi bir hesabın ele geçirilmesi tüm
    moderasyon ekibinin silinmesine yeterdi.

    KİŞİNİN KENDİ HESABINI SİLME HAKKI KAPANMIYOR: DELETE /api/auth/me
    yöneticiye de açık ve orada şifre doğrulaması var. Kapatılan şey, tek
    tıkla ve gerekçe kutusuyla yapılan kazara bir yönetici silmesi; bilinçli
    ve doğrulanmış silme yolu duruyor.
    """
    # Sıra önemli: yönetici kendisi de yönetici olduğu için önce "kendini"
    # kontrolü gelmeli, yoksa 400 yerine 403 dönerdi.
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail=f"Kendini {verb}.")
    if target.is_admin:
        raise HTTPException(
            status_code=403, detail=f"Başka bir yöneticiyi {verb}."
        )


@router.get("/users", response_model=list[AdminUserOut])
def admin_users(
    q: str | None = Query(
        None,
        max_length=254,
        description="E-posta VEYA ad içinde kısmi, harf duyarsız arama",
    ),
    suspended: bool | None = Query(
        None,
        description=(
            "true: askıdakiler, false: aktifler, boş: hepsi. "
            "Sonuç her hâlükârda sayfalıdır (limit/offset)."
        ),
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Kullanıcı listesi — arama ve sayfalama ile.

    FİLTRE NEDEN ARTIK ZORUNLU DEĞİL: `suspended` bir süre ZORUNLU tutuldu,
    çünkü uç eskiden filtresiz çağrıda tüm kullanıcı tabanını e-postalarıyla
    döküyordu. Asıl sorun filtrenin yokluğu değil, iki ayrı şeydi: sınırsız
    sayfa ve koşulsuz e-posta. İkisi de kapandı — sayfalama zorunlu (limit
    varsayılan 50), e-posta yalnız askıdaki hesaplar için dönüyor
    (_admin_user_row). Geriye kalan "tüm kullanıcılarda ada göre ara"
    ihtiyacı ise gerçek: bir bildirimde adı geçen kişiyi bulmanın başka yolu
    yoktu, çünkü askıda olup olmadığı zaten önceden bilinmiyor.

    ARAMA E-POSTAYA BAKAR AMA E-POSTAYI GÖSTERMEZ: "şu adresi bul" ihtiyacı,
    tüm adresleri listelemeyi gerektirmiyor (bkz. modül ilkesi 3).
    """
    stmt = select(models.User)
    if suspended is True:
        # Askıdakiler en son askıya alınan başta görünsün.
        stmt = stmt.where(models.User.is_suspended.is_(True)).order_by(
            models.User.suspended_at.desc(), models.User.id.desc()
        )
    elif suspended is False:
        stmt = stmt.where(models.User.is_suspended.is_(False)).order_by(
            models.User.id.desc()
        )
    else:
        stmt = stmt.order_by(models.User.id.desc())

    if q and q.strip():
        pattern = _search_pattern(q)
        stmt = stmt.where(
            _ilike(models.User.email, pattern) | _ilike(models.User.name, pattern)
        )

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [_admin_user_row(row) for row in rows]


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
    _protect_admin_accounts(target, admin, "askıya alamazsın")

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


@router.delete("/users/{user_id}", response_model=AdminDeleteOut)
def delete_user(
    user_id: int,
    payload: DeleteIn,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    """Hesabı ve ona bağlı tüm verileri KALICI siler — geri alınamaz.

    ÖNCE ASKIYA ALMAYI DÜŞÜN (POST /users/{id}/suspend): giriş kapanır,
    ilanları görünmez olur, hiçbir veri kaybolmaz ve karar yanlışsa geri
    alınır. Bu uç, askının yetmediği hâller için: silme talebi, gerçek kişiye
    ait veri, ısrarla yeniden açılan sahte hesap.

    NE SİLİNİR: ilanları, kaydırmaları, eşleşmeleri ve o eşleşmelerdeki
    mesajlar (karşı tarafınkiler dâhil — sohbetin yarısını bırakmanın anlamı
    yok), açtığı ve hedefi olduğu raporlar, oturumları. Başkalarının
    satırlarındaki denetim izleri SİLİNMEZ, yalnız aktörü NULL'a çekilir:
    kararın kendisi kalır, imzası gider.

    Silme mantığı auth.purge_user'da, DELETE /api/auth/me ile ORTAK. Ayrı iki
    liste tutulsaydı users.id'ye bakan yeni bir sütun eklendiğinde biri
    güncellenir öbürü unutulur ve o uç yabancı anahtar hatasıyla 500 verirdi
    (bu proje o hatayı üç kez yaşadı).

    Yöneticiler korumalıdır (bkz. _protect_admin_accounts).
    """
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    _protect_admin_accounts(target, admin, "silemezsin")

    # Satır gitmeden önce okunur; sonrasında hesabın kim olduğunu söyleyecek
    # başka bir kayıt kalmıyor. E-posta denetim kaydında SAKLANIR: "hangi
    # hesabı sildim" sorusunun cevabı yalnızca id ise, cevap yok demektir.
    detail = {
        "email": target.email,
        "name": target.name,
        "university": target.university,
        "was_suspended": bool(target.is_suspended),
        "created_at": target.created_at,
    }
    cleanup = purge_user(db, target)
    action = _record_action(
        db,
        admin,
        "user_delete",
        "user",
        user_id,
        reason=payload.reason,
        detail=detail,
    )
    db.commit()
    return {
        "kind": "user",
        "id": user_id,
        "deleted": True,
        "action_id": action.id,
        "cleanup": cleanup,
    }


# ---------------------------------------------------------------------------
# denetim kaydı
# ---------------------------------------------------------------------------

@router.get("/actions", response_model=list[AdminActionOut])
def admin_actions(
    action: str | None = Query(
        None, max_length=40, description="Tek bir eylem türüne süz"
    ),
    target_type: Literal["listing", "user"] | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Yönetici denetim kaydı, en yeni önce.

    Burada yalnızca GERİ ALINAMAZ eylemler ve önceki metni yok eden ilan
    düzenlemeleri var. Askıya alma, işaret temizleme, kaldırma ve geri alma
    izlerini kendi sütunlarında taşır; ilgili kuyruklardan okunur.

    Kaydın kendisi DEĞİŞTİRİLEMEZ: yazma ucu yok, silme ucu yok. Bir denetim
    kaydını düzenleyebilen yönetici için o kayıt hiçbir şey ifade etmezdi.
    """
    stmt = (
        select(models.AdminAction)
        .options(selectinload(models.AdminAction.actor))
        .order_by(
            models.AdminAction.created_at.desc(), models.AdminAction.id.desc()
        )
    )
    if action:
        stmt = stmt.where(models.AdminAction.action == action)
    if target_type is not None:
        stmt = stmt.where(models.AdminAction.target_type == target_type)

    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "actor_name": row.actor.name if row.actor else None,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "reason": row.reason,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]
