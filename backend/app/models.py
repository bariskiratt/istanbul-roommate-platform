"""Veritabanı tabloları."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Listing(Base):
    """Ev ilanı ("ev_ilani") veya kişisel ilan ("kisisel_ilan").

    Auth henüz olmadığı için sahiplik alanı yok; kullanıcı tablosu
    geldiğinde owner_id eklenecek.
    """

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(String(40), index=True)
    photos: Mapped[list] = mapped_column(JSON, default=list)

    # Ev ilanı alanları
    rent: Mapped[int | None] = mapped_column(Integer)
    room_count: Mapped[str | None] = mapped_column(String(10))
    smoking_allowed: Mapped[bool | None] = mapped_column(Boolean)
    pets_allowed: Mapped[bool | None] = mapped_column(Boolean)

    # Kişisel ilan alanları
    budget_min: Mapped[int | None] = mapped_column(Integer)
    budget_max: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
