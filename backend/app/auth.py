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
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.emailer import send_otp_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)

OTP_TTL = timedelta(minutes=10)
_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}


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


class UserUpdate(BaseModel):
    """PATCH /me — yalnızca gönderilen alanlar güncellenir."""

    name: str | None = Field(None, max_length=80)
    gender: str | None = Field(None, max_length=30)
    birth_year: int | None = Field(None, ge=1900, le=2100)
    university: str | None = Field(None, max_length=80)
    department: str | None = Field(None, max_length=80)
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
    return row.user if row else None


def get_current_user(
    user: models.User | None = Depends(get_optional_user),
) -> models.User:
    if user is None:
        raise HTTPException(status_code=401, detail="Giriş yapman gerekiyor.")
    return user


# ---- uçlar ----

@router.post("/register", status_code=201)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.scalar(
        select(models.User).where(models.User.email == payload.email)
    )
    if existing is not None:
        raise HTTPException(
            status_code=409, detail="Bu e-posta zaten kayıtlı. Giriş yap."
        )

    user = models.User(
        email=payload.email, password_hash=_hash_password(payload.password)
    )
    code = _issue_otp(user)
    db.add(user)
    response = _deliver_otp(payload.email, code)  # başarısızsa rollback
    db.commit()
    return response


@router.post("/request-otp")
def request_otp(payload: EmailIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if user is None:
        raise HTTPException(
            status_code=404, detail="Bu e-posta kayıtlı değil. Önce kayıt ol."
        )

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

    token = _issue_token(db, user)
    db.commit()
    return {"token": token, "user": user}


@router.post("/verify-otp", response_model=TokenOut)
def verify_otp(payload: VerifyIn, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == payload.email))
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
    if (
        "budget_min" in updates
        and "budget_max" in updates
        and updates["budget_min"] is not None
        and updates["budget_max"] is not None
        and updates["budget_min"] > updates["budget_max"]
    ):
        raise HTTPException(
            status_code=422, detail="Bütçe alt sınırı üst sınırdan büyük olamaz."
        )
    for key, value in updates.items():
        setattr(user, key, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
