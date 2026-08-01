"""Kimlik doğrulama: e-posta + şifre ile kayıt, OTP ile doğrulama/giriş.

E-posta servisi henüz bağlı değil; OTP kodu geliştirme kolaylığı için API
yanıtında `dev_code` alanında döner. Yayına çıkarken SMTP bağlanmalı ve
DEV_OTP=0 yapılmalı.

Token: opak rastgele dize; veritabanında yalnızca SHA-256 hash'i durur.
İstemci `Authorization: Bearer <token>` başlığıyla gönderir.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.departments import DEPARTMENT_GROUPS, is_valid as is_valid_department
from app.emailer import send_otp_email
from app.universities import university_from_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)

OTP_TTL = timedelta(minutes=10)
TOKEN_TTL = timedelta(days=30)

# Platform üniversite öğrencilerine yönelik
MIN_AGE, MAX_AGE = 17, 30

_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}

# Basit bellek-içi hız limiti: (uç, e-posta) başına pencere içi istek sayısı.
# Tek süreçli dağıtım için yeterli; restart'ta sıfırlanır.
RATE_LIMIT = 5
RATE_WINDOW = timedelta(minutes=15)
_RATE_BUCKETS: dict[tuple[str, str], list[datetime]] = {}


def _rate_limit(action: str, email: str) -> None:
    now = datetime.now(timezone.utc)
    bucket = _RATE_BUCKETS.setdefault((action, email), [])
    bucket[:] = [t for t in bucket if now - t < RATE_WINDOW]
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Çok fazla deneme yapıldı. 15 dakika sonra tekrar dene.",
        )
    bucket.append(now)


# Askıya alınmış hesap için verilen yanıt. Sebebi gizlemek kullanıcıyı neyi
# düzelteceğini bilmez hâlde bırakırdı; ama sebep YALNIZCA kimliğini
# kanıtlayana söylenir (bkz. _reject_if_suspended).
SUSPENDED_DETAIL = "Hesabın yönetici tarafından askıya alındı."


def _reject_if_suspended(user: models.User, *, include_reason: bool = False) -> None:
    """Askıdaki hesabın yeni oturum açmasını engeller (403).

    GEREKÇE YALNIZCA KİMLİĞİNİ KANITLAYANA GÖSTERİLİR (include_reason=True).

    suspended_reason yöneticinin kendi notudur ve serbest metindir: şüphenin
    ayrıntısını, hangi ihbara dayandığını, hatta IP/kimlik bilgisi
    taşıyabilir. Eskiden bu not KOŞULSUZ yanıta ekleniyordu; /request-otp ve
    /verify-otp ise kimlik doğrulamadan ÖNCE bu kontrolü çalıştırdığı için
    yalnızca e-posta adresini bilen bir yabancı, şifre ya da kod olmadan
    notun tamamını okuyabiliyordu:

        POST /api/auth/request-otp {"email": "..."}
        403 {"detail": "... Sebep: Dolandırıcılık şüphesi — IP Romanya"}

    Bu, moderasyon notunu hedefin kendisine değil HERKESE açıyordu; üstelik
    yöneticinin şüphesini ve bunu ihbar eden kişiyi ele verebilecek bir
    metindi (bkz. app/config.py, ilke 2-3).

    Şimdi gerekçeyi yalnızca /login döndürür — orada kontrol şifre
    doğrulandıktan SONRA çalışır, yani karşıdaki gerçekten hesabın sahibidir.
    Şifresiz uçlar (request-otp / verify-otp) genel cümleyle yetinir;
    kullanıcı gerekçeyi şifresiyle giriş deneyerek öğrenir.

    NOT: /verify-otp'ta askı kontrolü hâlâ kod doğrulamasından ÖNCE koşar —
    doğru kodu bilmek askıyı delmemeli. Değişen tek şey, o yanıtın artık
    yöneticinin notunu taşımaması.
    """
    if not user.is_suspended:
        return
    detail = SUSPENDED_DETAIL
    if include_reason and user.suspended_reason:
        detail = f"{detail} Sebep: {user.suspended_reason}"
    raise HTTPException(status_code=403, detail=detail)


# ---- kripto yardımcıları ----

def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), **_SCRYPT_PARAMS
    )
    return f"{salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), **_SCRYPT_PARAMS
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def _issue_otp(user: models.User) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.otp_hash = _sha256(code)
    user.otp_expires = datetime.now(timezone.utc) + OTP_TTL
    return code


def _dev_otp_enabled() -> bool:
    return os.getenv("DEV_OTP", "1") == "1"


def _deliver_otp(email: str, code: str) -> dict:
    """Kodu e-postayla yollar; dev modda yanıtta da döndürür.

    E-posta gönderilemedi VE dev modu kapalıysa hata fırlatır — çağıran
    henüz commit etmediği için kullanıcı kodsuz bırakılmaz.
    """
    sent = send_otp_email(email, code)
    if not sent and not _dev_otp_enabled():
        raise HTTPException(
            status_code=502,
            detail="Doğrulama e-postası gönderilemedi. Az sonra tekrar dene.",
        )
    response = {"detail": "Doğrulama kodu gönderildi."}
    if _dev_otp_enabled():
        response["dev_code"] = code
    return response


# ---- şemalar ----

class EmailIn(BaseModel):
    email: str = Field(..., min_length=6, max_length=254)

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return v


class RegisterIn(EmailIn):
    password: str = Field(..., min_length=8, max_length=128)


class VerifyIn(EmailIn):
    code: str = Field(..., min_length=6, max_length=6)


class LoginIn(EmailIn):
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    verified: bool
    name: str
    gender: str | None
    birth_year: int | None
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
    created_at: datetime
    is_admin: bool = False


class UserUpdate(BaseModel):
    """PATCH /me — yalnızca gönderilen alanlar güncellenir.

    `university` bilerek YOK: üniversite e-posta alan adından otomatik atanır
    ve elle değiştirilemez (doğrulanmış kimlik alanı). Gönderilirse Pydantic
    tarafından sessizce yok sayılır.
    """

    name: str | None = Field(None, max_length=80)
    gender: str | None = Field(None, max_length=30)
    birth_year: int | None = None
    department: str | None = Field(None, max_length=80)

    @field_validator("birth_year")
    @classmethod
    def _student_age(cls, v: int | None) -> int | None:
        # Platform üniversite öğrencilerine yönelik: 17-30 yaş
        if v is None:
            return v
        year = datetime.now(timezone.utc).year
        if not (year - MAX_AGE <= v <= year - MIN_AGE):
            raise ValueError(f"Yaş {MIN_AGE}-{MAX_AGE} aralığında olmalı.")
        return v

    @field_validator("department")
    @classmethod
    def _known_department(cls, v: str | None) -> str | None:
        # Bölüm kapalı listeden seçilir (bkz. app/departments.py)
        if not is_valid_department(v):
            raise ValueError("Bölüm listeden seçilmelidir.")
        return v
    year: int | None = Field(None, ge=1, le=10)
    budget_min: int | None = Field(None, gt=0, le=10_000_000)
    budget_max: int | None = Field(None, gt=0, le=10_000_000)
    smoking: bool | None = None
    pets: bool | None = None
    alcohol: bool | None = None
    sleep_schedule: str | None = Field(None, max_length=10)
    preferred_districts: list[str] | None = None
    bio: str | None = Field(None, max_length=2000)
    photos: list[str] | None = Field(None, max_length=6)


class TokenOut(BaseModel):
    token: str
    user: UserOut


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class AccountDelete(BaseModel):
    """Hesap silme onayı: şifre ya da geçerli OTP ile."""

    password: str = Field(..., min_length=1, max_length=128)


# ---- bağımlılıklar ----

def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> models.User | None:
    if credentials is None:
        return None
    row = db.scalar(
        select(models.AuthToken).where(
            models.AuthToken.token_hash == _sha256(credentials.credentials)
        )
    )
    if row is None:
        return None

    # Token yaşlandıysa geçersiz say ve temizle (30 gün)
    created = row.created_at
    if created is not None and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    if created is not None and datetime.now(timezone.utc) - created > TOKEN_TTL:
        db.delete(row)
        db.commit()
        return None

    # Askıya alınırken jetonlar zaten siliniyor; bu ikinci kapı, silme yarışı
    # veya elle veritabanı müdahalesi durumunda askının delinmesini önler.
    if row.user is not None and row.user.is_suspended:
        return None

    return row.user


def get_current_user(
    user: models.User | None = Depends(get_optional_user),
) -> models.User:
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş yapman gerekiyor.")
    return user


# ---- uçlar ----

@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    _rate_limit("register", payload.email)
    existing = db.scalar(
        select(models.User).where(models.User.email == payload.email)
    )
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Bu e-posta zaten kayıtlı. Giriş yap."
        )

    user = models.User(
        email=payload.email,
        password_hash=_hash_password(payload.password),
        # Üniversite e-posta alan adından otomatik dolar (bilinmiyorsa boş)
        university=university_from_email(payload.email),
    )
    code = _issue_otp(user)
    db.add(user)
    response = _deliver_otp(payload.email, code)  # başarısızsa rollback
    db.commit()
    return response


@router.post("/request-otp")
def request_otp(payload: EmailIn, db: Session = Depends(get_db)):
    _rate_limit("request-otp", payload.email)
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if user is None:
        raise HTTPException(
            status_code=404, detail="Bu e-posta kayıtlı değil. Önce kayıt ol."
        )
    # Askıdaki hesaba kod göndermenin anlamı yok; verify-otp zaten reddedecek.
    # Gerekçe EKLENMEZ: bu uç hiçbir kimlik doğrulaması istemiyor.
    _reject_if_suspended(user)

    code = _issue_otp(user)
    response = _deliver_otp(payload.email, code)  # başarısızsa rollback
    db.commit()
    return response


def _issue_token(db: Session, user: models.User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(models.AuthToken(user_id=user.id, token_hash=_sha256(token)))
    return token


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """E-posta + şifre ile giriş (OTP'siz)."""
    _rate_limit("login", payload.email)
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if (
        user is None
        or not user.password_hash
        or not _verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    if not user.verified:
        raise HTTPException(
            status_code=403,
            detail="Hesabın henüz doğrulanmamış. 'Kodla gir' ile e-postanı doğrula.",
        )
    # Şifre DOĞRULANDIKTAN sonra: karşıdaki hesabın sahibi, gerekçeyi görebilir.
    _reject_if_suspended(user, include_reason=True)

    token = _issue_token(db, user)
    db.commit()
    return {"token": token, "user": user}


@router.post("/verify-otp", response_model=TokenOut)
def verify_otp(payload: VerifyIn, db: Session = Depends(get_db)):
    # 6 haneli kodun kaba kuvvetle denenmesini engeller (5 deneme / 15 dk)
    _rate_limit("verify-otp", payload.email)
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    # Askı kontrolü koddan ÖNCE: doğru kodu bilmek askıyı delmemeli.
    # Gerekçe EKLENMEZ: buraya kod doğrulanmadan gelinebiliyor, yani karşıdaki
    # kişinin hesabın sahibi olduğu HENÜZ kanıtlanmadı.
    if user is not None:
        _reject_if_suspended(user)
    if user is None or user.otp_hash is None:
        raise HTTPException(status_code=400, detail="Önce kod iste.")

    expires = user.otp_expires
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)  # SQLite tz bilgisini düşürür
    if expires is None or expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Kodun süresi doldu. Yeni kod iste.")
    if not hmac.compare_digest(user.otp_hash, _sha256(payload.code)):
        raise HTTPException(status_code=400, detail="Kod hatalı.")

    user.verified = True
    user.otp_hash = None
    user.otp_expires = None

    token = _issue_token(db, user)
    db.commit()
    db.refresh(user)

    return {"token": token, "user": user}


@router.get("/departments")
def departments():
    """Profilde seçilebilecek bölümler (gruplu). Sabit liste, uzun cache."""
    return JSONResponse(
        DEPARTMENT_GROUPS,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = payload.model_dump(exclude_unset=True)
    # Tek alan güncellense bile tutarlılık mevcut değerle birlikte denetlenir
    eff_min = updates.get("budget_min", user.budget_min)
    eff_max = updates.get("budget_max", user.budget_max)
    if eff_min is not None and eff_max is not None and eff_min > eff_max:
        raise HTTPException(
            status_code=422, detail="Bütçe alt sınırı üst sınırdan büyük olamaz."
        )
    for key, value in updates.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChange,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Şifre değiştirir ve diğer tüm oturumları kapatır."""
    if not user.password_hash or not _verify_password(
        payload.current_password, user.password_hash
    ):
        raise HTTPException(status_code=400, detail="Mevcut şifren hatalı.")
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400, detail="Yeni şifre eskisiyle aynı olamaz."
        )

    user.password_hash = _hash_password(payload.new_password)
    # Güvenlik: şifre değişince tüm token'lar düşer, kullanıcı yeniden girer
    db.query(models.AuthToken).filter(
        models.AuthToken.user_id == user.id
    ).delete(synchronize_session=False)
    db.commit()


def _nullable_user_fk_columns() -> list:
    """users.id'ye işaret eden ve NULL kabul eden TÜM sütunlar.

    Liste elle tutulmaz, SQLAlchemy metadata'sından türetilir. Sebebi acı bir
    tekrardır: reports.reporter_id için bir kez düzeltilen "hesap silinemiyor"
    hatası, sonradan eklenen users.suspended_by / listings.reviewed_by /
    messages.reviewed_by / reports.resolved_by sütunlarıyla aynen geri geldi
    (yönetici tek bir moderasyon eylemi yapınca DELETE /api/auth/me
    IntegrityError ile 500 veriyordu). Bundan sonra eklenen her nullable
    yabancı anahtar bu süpürmeye kendiliğinden dahil olur.

    NULL'a çekmek denetim izinin AKTÖRÜNÜ kaybettirir (kararın kendisi,
    zamanı ve notu yerinde kalır). Bu bilinçli bir tercih: hesabını silme
    hakkı, o hesabın moderasyon geçmişindeki imzasından önce gelir.

    NOT NULL olan yabancı anahtarlar (swipes.swiper_id, matches.user_*_id,
    messages.sender_id, reports.reporter_id, auth_tokens.user_id) NULL'a
    çekilemez; onlar aşağıdaki açık silme sırasıyla temizlenir.
    """
    user_id_col = models.User.__table__.c.id
    return [
        column
        for table in models.Base.metadata.sorted_tables
        for column in table.columns
        if column.nullable
        and any(fk.column is user_id_col for fk in column.foreign_keys)
    ]


@router.delete("/me", status_code=204)
def delete_account(
    payload: AccountDelete,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hesabı ve ona bağlı tüm verileri kalıcı olarak siler."""
    if not user.password_hash or not _verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=400, detail="Şifren hatalı.")

    uid = user.id
    # Eşleşmelere ait mesajlar (karşı tarafınkiler dahil) önce silinmeli
    match_ids = [
        m.id
        for m in db.query(models.Match.id).filter(
            (models.Match.user_a_id == uid) | (models.Match.user_b_id == uid)
        )
    ]
    # messages.sender_id NOT NULL olduğu için kullanıcının yazdığı HER mesaj
    # silinmek zorunda. Normalde bunların hepsi zaten kendi eşleşmelerinin
    # içindedir; yine de match_id koşuluna güvenmiyoruz — tek bir artık satır
    # yabancı anahtar kısıtına takılıp hesap silmeyi 500'e çevirir.
    message_filter = models.Message.sender_id == uid
    if match_ids:
        message_filter = message_filter | models.Message.match_id.in_(match_ids)
    message_ids = [
        m.id for m in db.query(models.Message.id).filter(message_filter)
    ]
    if message_ids:
        db.query(models.Message).filter(
            models.Message.id.in_(message_ids)
        ).delete(synchronize_session=False)
    db.query(models.Match).filter(
        (models.Match.user_a_id == uid) | (models.Match.user_b_id == uid)
    ).delete(synchronize_session=False)

    listing_ids = [
        l.id for l in db.query(models.Listing.id).filter_by(owner_id=uid)
    ]
    if listing_ids:
        db.query(models.Swipe).filter(
            models.Swipe.listing_id.in_(listing_ids)
        ).delete(synchronize_session=False)
    db.query(models.Swipe).filter(models.Swipe.swiper_id == uid).delete(
        synchronize_session=False
    )
    db.query(models.Listing).filter_by(owner_id=uid).delete(
        synchronize_session=False
    )

    # Raporlar: reporter_id users.id'ye yabancı anahtarla bağlı — temizlenmezse
    # Postgres kısıtı hesabın silinmesini engeller (SQLite'ta FK varsayılan
    # kapalı olduğu için bu sessizce gözden kaçabiliyordu).
    db.query(models.Report).filter_by(reporter_id=uid).delete(
        synchronize_session=False
    )
    # Hedefi bu kullanıcı olan raporlar da silinir. target_id'de yabancı anahtar
    # YOK, yani teknik bir zorunluluk değil; karar şu gerekçeyle verildi:
    # inceleme konusu içerik artık yok, rapor açıldığında hedefi bulunamıyor.
    # Temizlenmezse yönetici kuyruğunda var olmayan bir kullanıcıyı/ilanı/mesajı
    # gösteren, tıklanınca 404 veren ölü kayıtlar birikir. Aynı gerekçeyle
    # kullanıcının silinen ilan ve mesajlarına açılmış raporlar da temizlenir.
    db.query(models.Report).filter(
        models.Report.target_type == "user", models.Report.target_id == uid
    ).delete(synchronize_session=False)
    if listing_ids:
        db.query(models.Report).filter(
            models.Report.target_type == "listing",
            models.Report.target_id.in_(listing_ids),
        ).delete(synchronize_session=False)
    if message_ids:
        db.query(models.Report).filter(
            models.Report.target_type == "message",
            models.Report.target_id.in_(message_ids),
        ).delete(synchronize_session=False)

    db.query(models.AuthToken).filter_by(user_id=uid).delete(
        synchronize_session=False
    )

    # Son adım: kullanıcıya işaret eden nullable yabancı anahtarları boşalt.
    # Bunlar denetim izi alanlarıdır (kim askıya aldı / kim inceledi / kim
    # raporu kapattı) ve silinen kullanıcı BAŞKALARININ satırlarında da
    # geçebilir; temizlenmezse hesap hiç silinemez. Açık silmelerden SONRA
    # koşar, böylece zaten silinmiş satırlar boşuna güncellenmez.
    for column in _nullable_user_fk_columns():
        db.execute(
            update(column.table).where(column == uid).values({column.name: None})
        )

    db.delete(user)
    db.commit()


@router.post("/logout", status_code=204)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        row = db.scalar(
            select(models.AuthToken).where(
                models.AuthToken.token_hash == _sha256(credentials.credentials)
            )
        )
        if row is not None:
            db.delete(row)
            db.commit()
