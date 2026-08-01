"""İlan CRUD uçları.

İlan oluşturma ve güncelleme giriş ister; metinler yayına girmeden önce
içerik denetiminden (app.moderation) geçer.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app import models, moderation
from app.auth import get_current_user, get_optional_user
from app.db import get_db

router = APIRouter(prefix="/api/listings", tags=["listings"])

ListingType = Literal["ev_ilani", "kisisel_ilan"]

# Ev özellikleri — şemalar ve "features" filtresi aynı listeden beslenir ki
# yeni bir özellik eklenince filtre kendiliğinden tanısın.
FEATURE_FIELDS: tuple[str, ...] = (
    "furnished",
    "elevator",
    "parking",
    "internet_included",
    "heating_included",
    "balcony",
    "natural_gas",
)


# Denetim reddinde hangi alanın sorunlu olduğu arayüze bu adlarla bildirilir.
_FIELD_LABELS = {"title": "Başlıkta", "description": "Açıklamada"}


def _reject(field: str, reasons: list[str]) -> HTTPException:
    """Alanı adıyla anan, yapılandırılmış 422 üretir.

    detail bir SÖZLÜKTÜR: arayüz `field` ile hatalı girdiyi işaretleyip
    kullanıcıyı doğru adıma götürebilsin diye. Metin sabit sözlükten gelir —
    KULLANICI GİRDİSİ hata mesajına asla yansıtılmaz.
    """
    label = _FIELD_LABELS.get(field, "Metinde")
    return HTTPException(
        status_code=422,
        detail={
            # describe() özneyi kendisi kurar; cümleyi elle kırpmak Türkçe'de
            # büyük İ'nin küçük harfe çevrilmesinde bozuk çıktı veriyor.
            "message": (
                f"{moderation.describe(reasons, subject=label)} "
                "Bu alanı düzenleyip tekrar deneyin."
            ),
            "field": field,
            "reasons": reasons,
        },
    )


def _moderate_field(text: str, field: str) -> moderation.ModerationResult:
    """Tek bir alanı denetler; engellenirse alanı adıyla anan 422 fırlatır."""
    # Kullanıcı sistemin ağzından konuşamaz: yönetici kuyruğunda ilan metni
    # olduğu gibi gösterildiği için sistem sabitleri yasak
    # (bkz. moderation.SYSTEM_MARKERS).
    if moderation.is_system_marker(text):
        raise HTTPException(
            status_code=422,
            detail={
                "message": moderation.SYSTEM_MARKER_REJECTION,
                "field": field,
                "reasons": [moderation.SYSTEM_MARKER],
            },
        )

    result = moderation.check(text, kind="listing")
    if result.blocked:
        raise _reject(field, result.reasons)
    return result


def _moderate(title: str, description: str) -> moderation.ModerationResult:
    """Başlığı ve açıklamayı AYRI AYRI denetler, sonuçları birleştirir.

    Ayrı denetlenmesinin tek sebebi geri bildirim: ikisi birleştirilip tek
    metin olarak denetlendiğinde kullanıcı hangi alanı düzelteceğini
    bilemiyordu. Kayıt üzerindeki işaret ve gerekçeler için sonuçlar yine
    tek bir sonuca indirgenir (moderation.merge).
    """
    return moderation.merge(
        _moderate_field(title, "title"),
        _moderate_field(description, "description"),
    )


def _suspended_user_ids():
    """Askıdaki kullanıcıların id'lerini veren alt sorgu."""
    return select(models.User.id).where(models.User.is_suspended.is_(True))


def _exclude_suspended_owners(stmt):
    """Askıdaki sahibin ilanlarını sorgudan eler.

    is_active'e DOKUNULMAZ: askı kalkınca ilanlar kendiliğinden geri gelir.
    owner_id NULL olan (auth öncesi anonim) ilanlar elenmemeli; SQL'de
    "NULL NOT IN (...)" NULL verdiği için açık OR şart.
    """
    return stmt.where(
        models.Listing.owner_id.is_(None)
        | models.Listing.owner_id.not_in(_suspended_user_ids())
    )


def _owner_suspended(row: models.Listing) -> bool:
    return row.owner is not None and bool(row.owner.is_suspended)


def _parse_features(raw: str | None) -> list[str]:
    """"features" sorgu parametresini ayrıştırır; geçersiz anahtarda 422 verir."""
    if not raw or not raw.strip():
        return []
    keys = [part.strip() for part in raw.split(",") if part.strip()]
    invalid = [k for k in keys if k not in FEATURE_FIELDS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Geçersiz özellik: {', '.join(invalid)}. "
                f"Geçerli anahtarlar: {', '.join(FEATURE_FIELDS)}."
            ),
        )
    # Tekrar eden anahtar aynı koşulu iki kez eklemesin.
    return list(dict.fromkeys(keys))


class ListingIn(BaseModel):
    type: ListingType
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    district: str = Field(..., min_length=1, max_length=40)
    # Mahalle isteğe bağlı: verilirse ve model tanıyorsa adil fiyat tahmini
    # mahalle bazında yapılır, yoksa ilçe geneline düşer (bkz. app/fairprice.py).
    neighborhood: str | None = Field(None, max_length=80)
    # En az 3 fotoğraf: tek fotoğraflı ilanlar hem güven vermiyor hem de
    # kaydırma destesinde ayırt edilemiyordu.
    photos: list[str] = Field(..., min_length=3, max_length=6)

    # Ev ilanı alanları
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None

    # Ev özellikleri — üç durumlu: True = var, False = yok, None = belirtilmemiş.
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None

    # Kişisel ilan alanları
    budget_min: int | None = Field(None, gt=0, le=10_000_000)
    budget_max: int | None = Field(None, gt=0, le=10_000_000)

    @model_validator(mode="after")
    def _check_type_fields(self):
        if self.type == "ev_ilani":
            if self.rent is None or not self.room_count:
                raise ValueError("Ev ilanı için kira ve oda sayısı zorunlu.")
        else:
            if self.budget_min is None or self.budget_max is None:
                raise ValueError("Kişisel ilan için bütçe aralığı zorunlu.")
            if self.budget_min > self.budget_max:
                raise ValueError("Bütçe alt sınırı üst sınırdan büyük olamaz.")
        return self


# NOT: ListingIn'den türetilmez — türetilirse tip doğrulayıcısı yanıt
# şemasında da koşar ve bozuk bir satır GET'leri 500'e düşürür.
class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: ListingType
    title: str
    description: str
    district: str
    neighborhood: str | None = None
    photos: list[str]
    rent: int | None
    room_count: str | None
    smoking_allowed: bool | None
    pets_allowed: bool | None
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None
    budget_min: int | None
    budget_max: int | None
    is_active: bool
    created_at: datetime
    owner_id: int | None = None
    owner_name: str | None = None
    owner_university: str | None = None


@router.post("", status_code=201, response_model=ListingOut)
def create_listing(
    payload: ListingIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """İlan oluşturma giriş ister — anonim ilan spam'ine kapalı."""
    result = _moderate(payload.title, payload.description)
    row = models.Listing(
        **payload.model_dump(),
        owner_id=user.id,
        is_flagged=result.flagged,
        flag_reasons=moderation.reasons_csv(result),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[ListingOut])
def list_listings(
    listing_type: ListingType | None = Query(None, alias="type"),
    district: str | None = Query(None, max_length=40),
    mine: bool = Query(False, description="Sadece kendi ilanlarım (giriş ister)"),
    unswiped: bool = Query(
        False, description="Daha önce kaydırdıklarımı ve kendi ilanlarımı gizle"
    ),
    features: str | None = Query(
        None,
        description=(
            "Virgülle ayrılmış ev özellikleri; hepsi işaretli olan ilanlar "
            "döner. Geçerli anahtarlar: " + ", ".join(FEATURE_FIELDS)
        ),
    ),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """Aktif ilanlar, en yeni önce."""
    stmt = (
        select(models.Listing)
        .options(joinedload(models.Listing.owner))  # owner_name için N+1 önlemi
        .where(models.Listing.is_active)
        .order_by(models.Listing.created_at.desc(), models.Listing.id.desc())
    )
    # Askıdaki kullanıcının ilanları hiçbir listede görünmez.
    stmt = _exclude_suspended_owners(stmt)
    if mine:
        if user is None:
            raise HTTPException(status_code=401, detail="Giriş yapman gerekiyor.")
        stmt = stmt.where(models.Listing.owner_id == user.id)
    if unswiped and user is not None:
        # Karar verilmiş ilanlar desteye geri gelmesin; kendi ilanları da çıkar
        swiped = select(models.Swipe.listing_id).where(
            models.Swipe.swiper_id == user.id
        )
        stmt = stmt.where(
            models.Listing.id.not_in(swiped),
            (models.Listing.owner_id != user.id) | models.Listing.owner_id.is_(None),
        )
    if listing_type is not None:
        stmt = stmt.where(models.Listing.type == listing_type)
    if district is not None:
        stmt = stmt.where(models.Listing.district == district)
    for key in _parse_features(features):
        # AND mantığı: istenen her özellik açıkça True olmalı; None
        # (belirtilmemiş) eşleşmez — kullanıcı "var" diyene bakıyor.
        # Ancak bu koşul YALNIZCA ev ilanlarına uygulanır: kişisel ilanlarda
        # (ev arayan kişi) asansör/otopark gibi ev özellikleri hiç olamaz,
        # dolayısıyla filtre onları elemek yerine kapsam dışı bırakır.
        stmt = stmt.where(
            (models.Listing.type != "ev_ilani")
            | getattr(models.Listing, key).is_(True)
        )
    return db.scalars(stmt).all()


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active or _owner_suspended(row):
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    return row


@router.get("/{listing_id}/fair-price")
def listing_fair_price(listing_id: int, db: Session = Depends(get_db)):
    """İlanın istediği oda payını modelin adil aralığıyla karşılaştırır.

    Ev arkadaşlığı dinamiği: yatak odaları kişiye özel, salon/mutfak/banyo
    ortaktır. Bu yüzden daire kirası yatak odası sayısına bölünür — "2+1"de
    iki kişi, salon kimseye fatura edilmez, ortak alan olarak paylaşılır.
    """
    from app.fairprice import estimate_for_listing  # döngüsel importu önler

    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active or _owner_suspended(row):
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.type != "ev_ilani" or row.rent is None:
        raise HTTPException(
            status_code=400, detail="Yalnızca ev ilanları için hesaplanır."
        )

    result = estimate_for_listing(
        row.district, row.room_count, row.rent, row.neighborhood
    )
    if result is None:
        raise HTTPException(
            status_code=503, detail="Adil fiyat modeli yüklü değil."
        )
    return result


class ListingUpdate(BaseModel):
    """PATCH — yalnızca gönderilen alanlar güncellenir; tip değiştirilemez."""

    title: str | None = Field(None, min_length=3, max_length=120)
    description: str | None = Field(None, min_length=1, max_length=2000)
    district: str | None = Field(None, min_length=1, max_length=40)
    neighborhood: str | None = Field(None, max_length=80)
    # Gönderilmezse dokunulmaz: alt sınırdan önce açılmış ilanlar bu yüzden
    # kilitlenmez, sahibi başlığını düzeltebilir. Gönderilirse kural aynı.
    photos: list[str] | None = Field(None, min_length=3, max_length=6)
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None
    furnished: bool | None = None
    elevator: bool | None = None
    parking: bool | None = None
    internet_included: bool | None = None
    heating_included: bool | None = None
    balcony: bool | None = None
    natural_gas: bool | None = None
    budget_min: int | None = Field(None, gt=0, le=10_000_000)
    budget_max: int | None = Field(None, gt=0, le=10_000_000)


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """İlan güncelleme — yalnızca ilan sahibi."""
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.owner_id is None or user is None or user.id != row.owner_id:
        raise HTTPException(status_code=403, detail="Bu ilan sana ait değil.")

    # null gönderilen alanlar "değiştirme" sayılır — zorunlu alanların
    # PATCH ile boşaltılıp kaydın bozulmasını engeller.
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

    # Denetim YALNIZCA metin gerçekten değişiyorsa çalışır.
    # Aksi hâlde: denetim kuralları ilan yayımlandıktan sonra sıkılaştığında,
    # eski metni bugünün kurallarına takılan bir ilanın sahibi kirasını,
    # fotoğrafını, hiçbir alanını güncelleyemez hâle geliyordu (422 kilidi).
    # Kullanıcı metne dokunmuyorsa yeni kuralı ona geriye dönük uygulamıyoruz;
    # başlık veya açıklama değişirse yeni hâl bir bütün olarak denetlenir.
    new_title = updates.get("title", row.title)
    new_description = updates.get("description", row.description)
    if new_title != row.title or new_description != row.description:
        result = _moderate(new_title, new_description)
        row.is_flagged = result.flagged
        row.flag_reasons = moderation.reasons_csv(result)

    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{listing_id}", status_code=204)
def deactivate_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Kalıcı silme yerine pasife çeker (satır ve veriler durur).

    DÜRÜSTLÜK NOTU: satır silinmediği için veri kaybı yoktur, ama sahibin
    kendi kapattığı ilanı YENİDEN YAYINA ALACAĞI BİR UÇ YOK — kapatma
    kullanıcı açısından tek yönlüdür. (Yöneticinin kaldırdığı ilan ayrı bir
    durumdur: moderation_removed=True olur ve
    POST /api/admin/listing/{id}/restore ile geri alınır.)

    Yalnızca ilan sahibi kapatabilir; sahipsiz (eski anonim) kayıtlar API'den
    silinemez, gerekirse veritabanından temizlenir.
    """
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    if row.owner_id is None or user.id != row.owner_id:
        raise HTTPException(status_code=403, detail="Bu ilan sana ait değil.")
    row.is_active = False
    db.commit()
