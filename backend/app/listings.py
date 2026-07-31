"""İlan CRUD uçları.

Auth henüz yok: ilanlar anonim oluşturulur. Kullanıcı sistemi geldiğinde
create ucu kimlik doğrulaması isteyecek ve owner_id yazacak.
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy.orm import joinedload

from app import models
from app.auth import get_current_user, get_optional_user
from app.db import get_db

router = APIRouter(prefix="/api/listings", tags=["listings"])

ListingType = Literal["ev_ilani", "kisisel_ilan"]


class ListingIn(BaseModel):
    type: ListingType
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    district: str = Field(..., min_length=1, max_length=40)
    photos: list[str] = Field(default_factory=list, max_length=6)

    # Ev ilanı alanları
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None

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
    photos: list[str]
    rent: int | None
    room_count: str | None
    smoking_allowed: bool | None
    pets_allowed: bool | None
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
    row = models.Listing(**payload.model_dump(), owner_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[ListingOut])
def list_listings(
    listing_type: ListingType | None = Query(None, alias="type"),
    district: str | None = Query(None, max_length=40),
    mine: bool = Query(False, description="Sadece kendi ilanlarım (giriş ister)"),
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
    if mine:
        if user is None:
            raise HTTPException(status_code=401, detail="Giriş yapman gerekiyor.")
        stmt = stmt.where(models.Listing.owner_id == user.id)
    if listing_type is not None:
        stmt = stmt.where(models.Listing.type == listing_type)
    if district is not None:
        stmt = stmt.where(models.Listing.district == district)
    return db.scalars(stmt).all()


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    return row


class ListingUpdate(BaseModel):
    """PATCH — yalnızca gönderilen alanlar güncellenir; tip değiştirilemez."""

    title: str | None = Field(None, min_length=3, max_length=120)
    description: str | None = Field(None, min_length=1, max_length=2000)
    district: str | None = Field(None, min_length=1, max_length=40)
    photos: list[str] | None = Field(None, max_length=6)
    rent: int | None = Field(None, gt=0, le=10_000_000)
    room_count: str | None = Field(None, max_length=10)
    smoking_allowed: bool | None = None
    pets_allowed: bool | None = None
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
    """Kalıcı silme yerine pasife çeker (geri alınabilir).

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
