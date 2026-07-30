"""Veritabanı tabloları."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Kayıtlı kullanıcı. E-posta + şifre ile kayıt, OTP ile doğrulama."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(200))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Profil (onboarding adımları)
    name: Mapped[str] = mapped_column(String(80), default="")
    gender: Mapped[str | None] = mapped_column(String(30))
    birth_year: Mapped[int | None] = mapped_column(Integer)
    university: Mapped[str | None] = mapped_column(String(80))
    department: Mapped[str | None] = mapped_column(String(80))
    year: Mapped[int | None] = mapped_column(Integer)
    budget_min: Mapped[int | None] = mapped_column(Integer)
    budget_max: Mapped[int | None] = mapped_column(Integer)
    smoking: Mapped[bool | None] = mapped_column(Boolean)
    pets: Mapped[bool | None] = mapped_column(Boolean)
    alcohol: Mapped[bool | None] = mapped_column(Boolean)
    sleep_schedule: Mapped[str | None] = mapped_column(String(10))
    preferred_districts: Mapped[list] = mapped_column(JSON, default=list)
    bio: Mapped[str] = mapped_column(Text, default="")
    photos: Mapped[list] = mapped_column(JSON, default=list)

    # Tek kullanımlık giriş kodu (hash'lenmiş; e-posta servisi bağlanana kadar
    # dev modda API yanıtında döner)
    otp_hash: Mapped[str | None] = mapped_column(String(64))
    otp_expires: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    listings: Mapped[list["Listing"]] = relationship(back_populates="owner")


class AuthToken(Base):
    """Opak Bearer token (hash'i saklanır). Çıkışta silinir."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User] = relationship()


class Listing(Base):
    """Ev ilanı ("ev_ilani") veya kişisel ilan ("kisisel_ilan").

    Auth henüz olmadığı için sahiplik alanı yok; kullanıcı tablosu
    geldiğinde owner_id eklenecek.
    """

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Anonim ilanlar (auth öncesi dönemden veya girişsiz) owner_id=None taşır.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), index=True
    )
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    owner: Mapped[User | None] = relationship(back_populates="listings")

    @property
    def owner_name(self) -> str | None:
        return self.owner.name if self.owner else None


class Swipe(Base):
    """Bir kullanıcının bir ilana verdiği karar (beğen/geç).

    Aynı ilana ikinci kez karar verilirse kayıt güncellenir (upsert).
    `responded`: ilan sahibi Beğeniler ekranında bu beğeniyi işledi mi.
    """

    __tablename__ = "swipes"
    __table_args__ = (UniqueConstraint("swiper_id", "listing_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    swiper_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    direction: Mapped[str] = mapped_column(String(10))  # like | pass
    responded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    swiper: Mapped[User] = relationship()
    listing: Mapped["Listing"] = relationship()


class Match(Base):
    """İki kullanıcı arasındaki eşleşme (çift başına tek kayıt).

    user_a_id < user_b_id olacak şekilde normalize edilir; böylece
    UniqueConstraint çift yönlü tekrarı engeller.
    """

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("user_a_id", "user_b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_a_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user_b_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Eşleşmeyi tetikleyen ilan (bağlam için; ilan kapansa da eşleşme yaşar)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user_a: Mapped[User] = relationship(foreign_keys=[user_a_id])
    user_b: Mapped[User] = relationship(foreign_keys=[user_b_id])
    listing: Mapped["Listing | None"] = relationship()


class Message(Base):
    """Eşleşme içindeki tek mesaj."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    match: Mapped[Match] = relationship()
    sender: Mapped[User] = relationship()
