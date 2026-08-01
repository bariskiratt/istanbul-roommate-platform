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

    # Yönetici askıya alması. Kalıcı silme yerine geri alınabilir bir kapı:
    # askıdaki kullanıcı giriş yapamaz ve ilanları genel listelerde görünmez,
    # ama hiçbir verisi silinmez (is_active'e de dokunulmaz).
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime)
    suspended_reason: Mapped[str | None] = mapped_column(String(500))
    # Hesap verebilirlik: askıya alan yöneticinin id'si.
    suspended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    # Askının KALDIRILMASI da bir eylemdir ve iz bırakır (bkz. admin.py ilke 4).
    # Eskiden askı kalkınca suspended_* alanları NULL'a çekiliyordu; geriye
    # hiçbir kayıt kalmadığı için "bu hesap neden askıya alınmıştı, kim geri
    # aldı" sorusu cevapsızdı. Artık gerekçe silinmez, GEÇMİŞE TAŞINIR.
    unsuspended_at: Mapped[datetime | None] = mapped_column(DateTime)
    unsuspended_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Askı kalkarken suspended_reason buraya taşınır. Aktif kullanıcıda
    # suspended_reason dolu kalsaydı arayüz yürürlükte olmayan bir gerekçeyi
    # yürürlükteymiş gibi gösterirdi.
    last_suspension_reason: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="owner", foreign_keys="Listing.owner_id"
    )

    @property
    def is_admin(self) -> bool:
        from app.config import ADMIN_EMAILS

        return self.email.lower() in ADMIN_EMAILS


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
    # Mahalle ("Caferağa Mah."). Zorunlu değil: bu sütun gelmeden önce açılan
    # ilanlarda NULL kalır ve adil fiyat tahmini onlarda ilçe geneline düşer.
    neighborhood: Mapped[str | None] = mapped_column(String(80))
    photos: Mapped[list] = mapped_column(JSON, default=list)

    # Ev ilanı alanları
    rent: Mapped[int | None] = mapped_column(Integer)
    room_count: Mapped[str | None] = mapped_column(String(10))
    smoking_allowed: Mapped[bool | None] = mapped_column(Boolean)
    pets_allowed: Mapped[bool | None] = mapped_column(Boolean)

    # Ev özellikleri (yalnızca ev ilanı). Hepsi üç durumlu:
    # True = var, False = yok, None = belirtilmemiş.
    furnished: Mapped[bool | None] = mapped_column(Boolean)
    elevator: Mapped[bool | None] = mapped_column(Boolean)
    parking: Mapped[bool | None] = mapped_column(Boolean)
    internet_included: Mapped[bool | None] = mapped_column(Boolean)
    heating_included: Mapped[bool | None] = mapped_column(Boolean)
    balcony: Mapped[bool | None] = mapped_column(Boolean)
    natural_gas: Mapped[bool | None] = mapped_column(Boolean)

    # Kişisel ilan alanları
    budget_min: Mapped[int | None] = mapped_column(Integer)
    budget_max: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Yönetici "yayından kaldır" dediğinde True olur (is_active da False olur).
    # Sahibin kendi kapattığı ilandan ayırt etmek için ŞART: ikisinde de
    # is_active False'tur, ama yalnız bunu yönetici geri alabilir
    # (POST /api/admin/listing/{id}/restore) ve yalnız bu
    # /api/admin/flagged?status=removed kuyruğunda görünür.
    moderation_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Yönetici kaldırdığı AN ilan yayında mıydı. Geri alma buraya döner.
    #
    # Neden gerekli: işaretlenmiş bir ilanı sahibi kendi kapatmışsa
    # (is_active False, moderation_removed False) kayıt inceleme kuyruğunda
    # durmaya devam eder; yönetici oradan "kaldır" derse moderation_removed
    # True olur. Bu sütun olmadan geri alma is_active'i KOŞULSUZ True yapıyor
    # ve sahibin kendi kapatma kararını eziyordu — ilan sahibi hiç istemeden
    # yeniden yayına giriyordu. Artık geri alma, kaldırmadan önceki hâle
    # döner: yayındaysa yayına, kapalıysa kapalı.
    #
    # NULL = bu sütun eklenmeden önce kaldırılmış eski kayıt; o kayıtlarda
    # önceki durum bilinmiyor, geri alma eski davranışa (yayına al) düşer.
    active_before_removal: Mapped[bool | None] = mapped_column(Boolean)
    # İçerik denetimi "flag" dediğinde işaretlenir; ilan yayında kalır ama
    # yönetici incelemesine düşer.
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    # Denetimin verdiği sebep kodları, virgülle ayrılmış ("kufur,taciz:tehdit").
    # İşaretlemenin gerekçesi kaydedilmezse yönetici neye baktığını bilemez.
    # Bu sütun eklenmeden önce işaretlenmiş kayıtlarda NULL kalır.
    flag_reasons: Mapped[str | None] = mapped_column(Text)
    # Yönetici incelemesi (temizle / yayından kaldır)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    owner: Mapped[User | None] = relationship(
        back_populates="listings", foreign_keys=[owner_id]
    )

    @property
    def owner_name(self) -> str | None:
        return self.owner.name if self.owner else None

    @property
    def owner_university(self) -> str | None:
        return self.owner.university if self.owner else None


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
    """Eşleşme içindeki tek mesaj.

    `content` sunucuda şifreli saklanır (app.crypto, AES-256-GCM). Anahtar
    sunucuda olduğu için bu UÇTAN UCA şifreleme DEĞİLDİR. Anahtar tanımlı
    değilken ve eski kayıtlarda düz metin bulunabilir.
    """

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str] = mapped_column(Text)
    # Yönetici "içeriği kaldır" dediğinde: mevcut content OLDUĞU GİBİ (yani
    # şifreliyse şifreli hâliyle) buraya taşınır, content sabitle değiştirilir.
    # "restore" metni buradan geri koyar ve alanı boşaltır. Alan doluyken
    # yalnızca yönetici uçları okur; sohbet uçları her zaman content'i döner.
    original_content: Mapped[str | None] = mapped_column(Text)
    # Yönetici "içeriği kaldır" dediğinde True; "restore" ile False olur.
    moderation_removed: Mapped[bool] = mapped_column(Boolean, default=False)
    # İçerik denetimi "flag" dediğinde işaretlenir; mesaj iletilir ama
    # yönetici incelemesine düşer.
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    # bkz. Listing.flag_reasons — aynı biçim (virgülle ayrılmış sebep kodları).
    flag_reasons: Mapped[str | None] = mapped_column(Text)
    # Yönetici incelemesi (temizle / içeriği kaldır)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    match: Mapped[Match] = relationship()
    sender: Mapped[User] = relationship(foreign_keys=[sender_id])


class Report(Base):
    """Kullanıcı şikâyeti (ilan / kullanıcı / mesaj).

    Aynı kullanıcının aynı hedefi tekrar tekrar raporlamasını UniqueConstraint
    engeller; ikinci istek 409 ile reddedilir (bkz. app/reports.py).
    """

    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # "listing" | "user" | "message"
    target_type: Mapped[str] = mapped_column(String(20), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    # Kapalı liste: spam | dolandiricilik | taciz | uygunsuz_icerik |
    # sahte_ilan | diger
    reason: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_note: Mapped[str | None] = mapped_column(String(500))
    # Hesap verebilirlik: raporu kim, ne zaman kapattı.
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
