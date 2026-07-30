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

from app import models
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


class ListingOut(ListingIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


@router.post("", status_code=201, response_model=ListingOut)
def create_listing(payload: ListingIn, db: Session = Depends(get_db)):
    row = models.Listing(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[ListingOut])
def list_listings(
    listing_type: ListingType | None = Query(None, alias="type"),
    district: str | None = Query(None, max_length=40),
    db: Session = Depends(get_db),
):
    """Aktif ilanlar, en yeni önce."""
    stmt = (
        select(models.Listing)
        .where(models.Listing.is_active)
        .order_by(models.Listing.created_at.desc(), models.Listing.id.desc())
    )
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


@router.delete("/{listing_id}", status_code=204)
def deactivate_listing(listing_id: int, db: Session = Depends(get_db)):
    """Kalıcı silme yerine pasife çeker (geri alınabilir)."""
    row = db.get(models.Listing, listing_id)
    if row is None or not row.is_active:
        raise HTTPException(status_code=404, detail="İlan bulunamadı.")
    row.is_active = False
    db.commit()
