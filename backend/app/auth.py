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
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app import config, models
from app.db import get_db
from app.departments import DEPARTMENT_GROUPS, is_valid as is_valid_department
from app.emailer import send_otp_email
from app.universities import DOMAINS as UNIVERSITY_DOMAINS, university_from_email

router = APIRouter(prefix="/api/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)

OTP_TTL = timedelta(minutes=10)
TOKEN_TTL = timedelta(days=30)

# Platform üniversite öğrencilerine yönelik
MIN_AGE, MAX_AGE = 17, 30

_SCRYPT_PARAMS = {"n": 2**14, "r": 8, "p": 1}

# ---- hız limiti ----
#
# Basit bellek-içi sayaç: kova anahtarı başına pencere içi istek sayısı.
# Tek süreçli dağıtım için yeterli; restart'ta sıfırlanır. (Birden çok
# worker'a çıkılırsa bu sayaç süreç başına ayrı tutulacağı için gerçek limit
# worker sayısıyla çarpılır — o noktada Redis'e taşınmalı.)
RATE_LIMIT = 5
RATE_WINDOW = timedelta(minutes=15)

# IP BAŞINA KAYIT LİMİTİ.
#
# E-posta anahtarlı sayaç kütle kaydı hiç engellemiyordu: her istekte farklı
# bir adres kullanan bir betik tek oturumda onlarca hesap açabiliyordu (yerelde
# tek IP'den 80 kayıt denendi, hepsi 201 döndü). Sahte hesap üretimi bu üründe
# doğrudan taciz/dolandırıcılık kapısı olduğu için ikinci bir boyut şart.
#
# Aynı sayaç e-posta taramasını da pahalılaştırıyor: /register hâlâ 409 ile
# "bu adres kayıtlı" diyor (kayıt akışını bozmamak için bilerek korundu), ama
# saatte 10 tahminle liste taramak anlamsız.
#
# Değer seçimi: yurt/kampüs NAT'ı arkasından birden çok öğrencinin aynı IP ile
# kayıt olması normaldir, o yüzden 5 değil 10; pencere de 15 dakika değil
# 1 saat, çünkü kütle kayıt yavaşlatılınca değil ancak uzun pencerede durur.
REGISTER_IP_LIMIT = 10
REGISTER_IP_WINDOW = timedelta(hours=1)

# IP başına kod isteme limiti. Amaç e-posta bombardımanı: /request-otp
# başkasının adresine posta gönderten tek uç, e-posta anahtarlı sayaç ise
# saldırganın her istekte başka bir kurban seçmesini engellemiyor.
OTP_IP_LIMIT = 15
OTP_IP_WINDOW = timedelta(hours=1)

_RATE_BUCKETS: dict[tuple[str, ...], list[datetime]] = {}

# Kovaların budanması (L2). Sözlük eskiden hiç temizlenmiyordu: her yeni
# e-posta/IP ikilisi kalıcı bir giriş açtığı için uzun süre ayakta kalan bir
# süreçte bu sözlük sınırsız büyüyordu — kayıt ucunu döven biri onu tek başına
# şişirebilirdi. Artık pencereden çıkmış kovalar atılıyor.
_BUCKET_TTL = max(RATE_WINDOW, REGISTER_IP_WINDOW, OTP_IP_WINDOW)
_PRUNE_INTERVAL = timedelta(minutes=1)
# Bu sayının üstünde budama beklemeden hemen koşar (sel altında TTL yetmez).
_MAX_BUCKETS = 10_000
_last_prune = datetime.min.replace(tzinfo=timezone.utc)


def _prune_buckets(now: datetime) -> None:
    """Süresi geçmiş kovaları atar. Amortize: dakikada bir ya da sözlük
    büyüdüğünde koşar, her istekte değil."""
    global _last_prune
    if (
        now - _last_prune < _PRUNE_INTERVAL
        and len(_RATE_BUCKETS) < _MAX_BUCKETS
    ):
        return
    _last_prune = now
    for key, stamps in list(_RATE_BUCKETS.items()):
        if not stamps or now - stamps[-1] >= _BUCKET_TTL:
            del _RATE_BUCKETS[key]
    # Budamaya rağmen tavanın üstündeysek (hepsi taze, yani aktif bir sel var)
    # en eskiden başlayarak kırp: bellek tüketimi her hâlükârda sınırlı kalmalı.
    if len(_RATE_BUCKETS) > _MAX_BUCKETS:
        for key, _ in sorted(
            _RATE_BUCKETS.items(), key=lambda kv: kv[1][-1]
        )[: len(_RATE_BUCKETS) - _MAX_BUCKETS]:
            del _RATE_BUCKETS[key]


def _too_many(window: timedelta) -> HTTPException:
    minutes = max(1, int(window.total_seconds() // 60))
    unit = f"{minutes // 60} saat" if minutes >= 60 else f"{minutes} dakika"
    return HTTPException(
        status_code=429,
        detail=f"Çok fazla deneme yapıldı. {unit} sonra tekrar dene.",
    )


def _rate_limit(
    action: str,
    *parts: str,
    limit: int = RATE_LIMIT,
    window: timedelta = RATE_WINDOW,
) -> None:
    """Kovayı bir istek ilerletir; limit aşıldıysa 429 fırlatır.

    Anahtar serbest sayıda parçadan oluşur — çağıran e-posta, IP ya da ikisini
    birden verebilir. Boyut seçimi güvenlik kararıdır, bkz. uçlardaki notlar.
    """
    now = datetime.now(timezone.utc)
    _prune_buckets(now)
    bucket = _RATE_BUCKETS.setdefault((action, *parts), [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        raise _too_many(window)
    bucket.append(now)


def _reset_rate_limit(action: str, *parts: str) -> None:
    """Kovayı tamamen sıfırlar (başarılı girişten sonra)."""
    _RATE_BUCKETS.pop((action, *parts), None)


def _client_ip(request: Request) -> str:
    """İsteğin kaynak IP'si.

    X-Forwarded-For YALNIZCA config.TRUST_PROXY_HEADERS açıkken okunur:
    başlık istemci tarafından uydurulabilir, her istekte başka bir değer
    göndermek IP limitini tamamen anlamsız kılar. Ters vekil arkasında
    değilsen (varsayılan) doğrudan soketin adresi kullanılır.
    """
    if config.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # EN SAĞDAKİ değer alınır, en soldaki DEĞİL.
            #
            # X-Forwarded-For soldan sağa büyür: her vekil kendinden önceki
            # adresi sona ekler. İstemci de kendi başlığını gönderebilir, o
            # yüzden SOLDAKİ değer saldırgan tarafından uydurulabilir —
            # soldan okumak IP limitini tamamen anlamsız kılardı (her istekte
            # başka bir "IP" yazıp sınırsız deneme yapılabilirdi).
            #
            # Bu kurulumda uygulamanın önünde TEK vekil var (Render), yani
            # bize ulaşan zincirin son elemanını yazan odur ve güvenilirdir.
            # Vekil sayısı değişirse burası da değişmeli.
            return forwarded.split(",")[-1].strip()[:64] or "bilinmiyor"
    return request.client.host if request.client else "bilinmiyor"


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


# ---- OTP saklama ----
#
# OTP 6 HANEDİR, yani arama uzayı 10^6. Düz SHA-256 ile saklandığında bu
# "hash" hiçbir şey gizlemez: veritabanını, bir yedeği ya da parametreleri
# sızdıran bir log satırını gören biri bir milyon adayı saniyeler içinde
# deneyip kodu geri bulur ve /verify-otp ile hesabı devralır (şifre hiç
# gerekmez). Tuz eklemek de yetmez — tuz satırın yanında durur.
#
# Çözüm: SUNUCUDA DURAN bir sırla HMAC. Sır veritabanında olmadığı için
# yalnızca DB'yi ele geçiren saldırgan kodu geri bulamaz.
#
# Sır yoksa bugünkü davranışa (düz SHA-256) DÜŞÜLÜR ve bir kez uyarı basılır;
# yerel geliştirme kırılmasın diye. Aynı desen MESSAGE_KEY'de de kullanılıyor
# (bkz. app/crypto.py) — oradaki gibi kısa/zayıf değerler kabul edilmez.
OTP_KEY_ENV = "OTP_KEY"
MIN_OTP_KEY_LENGTH = 32

_otp_key: bytes | None = None
_otp_key_loaded = False
_otp_warned: set[str] = set()


def _otp_warn_once(message: str) -> None:
    if message in _otp_warned:
        return
    _otp_warned.add(message)
    print(f"⚠️  {message}", flush=True)


def reset_otp_key_cache() -> None:
    """Sır önbelleğini temizler — testlerde ortam değişkeni değiştirmek için."""
    global _otp_key, _otp_key_loaded
    _otp_key = None
    _otp_key_loaded = False
    _otp_warned.clear()


def otp_key_available() -> bool:
    """OTP kodları HMAC ile mi saklanıyor (yani OTP_KEY geçerli mi)?

    Dağıtım sonrası doğrulama için: crypto.key_available() ile aynı işi görür.
    False dönerse kodlar tuzsuz SHA-256 ile saklanıyor demektir.
    """
    return _otp_key_bytes() is not None


def _otp_key_bytes() -> bytes | None:
    global _otp_key, _otp_key_loaded
    if _otp_key_loaded:
        return _otp_key
    _otp_key_loaded = True

    raw = os.getenv(OTP_KEY_ENV, "").strip()
    if not raw:
        _otp_warn_once(
            f"{OTP_KEY_ENV} tanımlı değil — OTP kodları tuzsuz SHA-256 ile "
            f"saklanacak. 6 hane = 10^6 arama uzayı; veritabanını gören biri "
            f"kodu geri bulabilir. Üretimde MUTLAKA tanımla "
            f"(en az {MIN_OTP_KEY_LENGTH} karakter rastgele dize)."
        )
        return None
    if len(raw) < MIN_OTP_KEY_LENGTH:
        _otp_warn_once(
            f"{OTP_KEY_ENV} çok kısa ({len(raw)} karakter; en az "
            f"{MIN_OTP_KEY_LENGTH} gerekir) — tuzsuz SHA-256'ya düşülüyor."
        )
        return None
    _otp_key = raw.encode()
    return _otp_key


def _otp_digest(code: str) -> str:
    """Saklanacak OTP özeti: sır varsa HMAC-SHA256, yoksa düz SHA-256."""
    key = _otp_key_bytes()
    if key is None:
        return _sha256(code)
    return hmac.new(key, code.encode(), hashlib.sha256).hexdigest()


def _otp_matches(stored: str, code: str) -> bool:
    """Kod, saklanan özetle uyuşuyor mu?

    HMAC'in yanında ESKİ düz SHA-256 biçimi de kabul edilir: OTP_KEY yeni
    tanımlandığında o an dolaşımda olan (en fazla 10 dakikalık) kodlar eski
    biçimde saklanmıştır ve kullanıcı doğrulamayı yarıda bırakmamalıdır.
    İki karşılaştırma da sabit zamanlıdır; eski biçimi kabul etmek yeni
    kodların güvenliğini düşürmez, çünkü hangi biçimin geçerli olduğunu
    saldırgan değil SATIRDAKİ DEĞER belirler.
    """
    if hmac.compare_digest(stored, _otp_digest(code)):
        return True
    return hmac.compare_digest(stored, _sha256(code))


def _issue_otp(user: models.User) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.otp_hash = _otp_digest(code)
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

def is_student_email(email: str) -> bool:
    """Adres bir Türk üniversitesi öğrenci/personel adresi mi?

    KABUL EDİLENLER
      1. Alan adı "edu.tr" ya da ".edu.tr" ile biten her adres — Türkiye'de
         edu.tr alt alanları yalnızca YÖK'e bağlı kurumlara verilir, yani
         bu kural "üniversiteye ait adres" için makul bir vekildir.
      2. app/universities.py DOMAINS listesindeki alan adları ve alt alanları.
         Bu ikinci kural tek bir somut boşluk için var: sabanciuniv.edu
         (ve ileride eklenebilecek benzerleri) tanınan bir Türk üniversitesi
         alan adı olduğu hâlde .edu.tr DEĞİLDİR. Yalnızca birinci kural
         uygulansaydı o üniversitenin öğrencileri kapıda kalırdı — üstelik
         üniversiteleri sistemde zaten tanımlı olduğu için sessizce.

    Muafiyet (config.ADMIN_EMAILS) burada DEĞİL, çağıran doğrulayıcıda
    uygulanır; bu fonksiyon saf bir "öğrenci adresi mi" testidir.
    """
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if not domain:
        return False
    if domain == "edu.tr" or domain.endswith(".edu.tr"):
        return True
    return any(
        domain == known or domain.endswith("." + known)
        for known in UNIVERSITY_DOMAINS
    )


STUDENT_EMAIL_ERROR = (
    "Yalnızca üniversite e-posta adresiyle (.edu.tr) kayıt olunabilir. "
    "Okulunun sana verdiği adresi kullan."
)


class EmailIn(BaseModel):
    """Adresi yalnızca NORMALİZE eder; alan adı kısıtı UYGULAMAZ.

    Giriş, kod isteme ve kod doğrulama bunu kullanır. Kısıtın burada
    olmaması bilinçlidir: kural kimin HESAP AÇABİLECEĞİNİ belirler, kimin
    var olan hesabına GİREBİLECEĞİNİ değil. Kısıt giriş ucuna da uygulanınca
    kuraldan önce kaydolmuş herkes (demo hesapları ve gerçek kullanıcılar)
    kendi hesabından kilitlendi — üretimde yaşandı. Hesap ya vardır ya
    yoktur; adresini yeniden yargılamak yalnızca sahibini dışarıda bırakır.
    """

    email: str = Field(..., min_length=6, max_length=254)

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        return v


class StudentEmailIn(EmailIn):
    email: str = Field(..., min_length=6, max_length=254)

    @field_validator("email")
    @classmethod
    def _normalize(cls, v: str) -> str:
        """Adresi normalize eder ve ÖĞRENCİ ADRESİ olmasını zorlar.

        Bu kural eskiden yalnızca tarayıcıdaki bir if'ti (Onboarding.tsx).
        API'ye doğrudan istek atan biri gmail adresiyle kayıt olup OTP'yi
        doğrulayarak tam yetkili hesap açabiliyordu — oysa ürün ".edu.tr
        zorunlu" ifadesini bir GÜVENLİK GÜVENCESİ olarak pazarlıyor (arayüzün
        güvenlik metinleri ve Safety sayfası). Yani doğrulama eksik değil,
        kullanıcıya verilen söz yalandı. Kural artık sunucuda.

        MUAFİYET: config.ADMIN_EMAILS adresleri geçer. Yöneticinin
        adreslerinden biri gmail.com ve is_admin tamamen e-posta eşleşmesine
        bağlı; muafiyet olmasaydı yönetici kendi hesabını hiç açamaz, sistem
        moderatörsüz kalırdı. Liste işletmecinin kontrolündeki bir ortam
        değişkeninden gelir, dışarıdan kimse ekleyemez (bkz. app/config.py).
        """
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin.")
        if v in config.ADMIN_EMAILS:
            return v
        if not is_student_email(v):
            raise ValueError(STUDENT_EMAIL_ERROR)
        return v


class RegisterIn(StudentEmailIn):
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


# LİSTE ALANLARININ SINIRLARI — HEM ÖĞE SAYISI HEM ÖĞE UZUNLUĞU.
#
# Eskiden photos yalnızca ELEMAN SAYISIYLA (6) sınırlıydı, preferred_districts
# ise hiç sınırlı değildi. Öğe uzunluğu serbest kalınca sayı sınırı bir şey
# ifade etmiyor: 6 tane 2 MB'lık dize gönderen bir PATCH kabul ediliyor ve tek
# kullanıcı satırı 32 MB'a çıkıyordu. Bu satır sonra HER profil/ilan
# yanıtında okunup ağdan geçtiği için, tek bir yazma isteği kalıcı bir
# bant genişliği ve bellek yükü bırakıyordu (anonim GET /api/listings 12 MB
# döndürebiliyordu).
#
# Değerler gerçek kullanıma göre seçildi: İstanbul ilçe adlarının en uzunu
# 20 karakterin altında (40 bol bir tavan), kendi ürettiğimiz fotoğraf URL'i
# ~90 karakter; 500 dış barındırıcıların uzun sorgu dizelerine yer bırakır.
MAX_DISTRICTS = 10
MAX_DISTRICT_LENGTH = 40
MAX_PHOTOS = 6
MAX_PHOTO_URL_LENGTH = 500

DistrictName = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=MAX_DISTRICT_LENGTH)
]
PhotoUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=MAX_PHOTO_URL_LENGTH)
]


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
    preferred_districts: list[DistrictName] | None = Field(
        None, max_length=MAX_DISTRICTS
    )
    bio: str | None = Field(None, max_length=2000)
    photos: list[PhotoUrl] | None = Field(None, max_length=MAX_PHOTOS)


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
def register(
    payload: RegisterIn, request: Request, db: Session = Depends(get_db)
):
    ip = _client_ip(request)
    # İki boyut birden: e-posta sayacı aynı adresin dövülmesini, IP sayacı
    # HER İSTEKTE BAŞKA adres kullanan kütle kaydı/adres taramasını durdurur.
    _rate_limit("register", payload.email)
    _rate_limit(
        "register-ip",
        ip,
        limit=REGISTER_IP_LIMIT,
        window=REGISTER_IP_WINDOW,
    )
    existing = db.scalar(
        select(models.User).where(models.User.email == payload.email)
    )
    if existing is not None:
        # 409 BİLEREK KORUNDU (e-posta numaralandırmasına açık olduğu hâlde).
        #
        # Tekdüze yanıt vermek burada kayıt akışını bozar: adres zaten
        # kayıtlıysa ve 201 dönersek, kullanıcı gelmeyecek bir kodu bekler;
        # "kayıt oldum ama kod gelmedi" desteğe düşer. Alternatif olan "sessizce
        # var olan hesaba kod gönder" ise daha kötüsü — bir yabancı, başkasının
        # adresiyle kayıt olmaya çalışarak o hesaba giriş kodu tetikleyebilir.
        #
        # Bunun yerine sızıntının DEĞERİ düşürüldü: yukarıdaki IP sayacı
        # sayesinde tarama saatte 10 adresle sınırlı, yani liste taramak
        # pratikte işe yaramıyor. Gerçek numaralandırma kapısı olan
        # /request-otp'un 404'ü ise kaldırıldı (bkz. request_otp).
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
def request_otp(payload: EmailIn, request: Request, db: Session = Depends(get_db)):
    """Giriş kodu ister. YANIT, ADRESİN KAYITLI OLUP OLMADIĞINI SÖYLEMEZ.

    Eskiden kayıtlı olmayan adres için 404 "Bu e-posta kayıtlı değil"
    dönüyordu. Bu, kimlik doğrulaması istemeyen bir uçtan ÜYELİK SORGUSUdur:
    elindeki adres listesini tek tek deneyen biri, kimin bu platformda hesabı
    olduğunu öğrenir. Ev arkadaşı arama platformunda üyeliğin kendisi hassas
    bir bilgidir (kişinin taşınmak istediğini, muhtemelen bütçesini ve
    üniversitesini ima eder) ve e-posta anahtarlı hız limiti bu taramayı hiç
    yavaşlatmıyordu — her istek FARKLI bir adresle geliyor.

    Artık iki durumda da aynı 200 ve aynı metin döner; kod yalnızca gerçekten
    kayıtlı adrese gider. Bedeli: adresini yanlış yazan kullanıcı "kod
    gönderildi" görüp bekler. Bunu kabul ediyoruz çünkü kayıt akışında
    (/register) yanlış adres zaten 201 ile ilerliyor ve kullanıcı kodu
    alamayınca tekrar deniyor; buradaki tek fark hatanın bir istek geç fark
    edilmesi.

    dev_code de yalnızca gerçek kullanıcı için döner — aksi hâlde yanıtın
    varlığı/yokluğu numaralandırmayı geri getirirdi.
    """
    ip = _client_ip(request)
    _rate_limit("request-otp", payload.email)
    # IP boyutu: e-posta sayacı, her istekte başka bir kurban seçen birini
    # engellemiyor. Bu uç başkasının gelen kutusuna posta gönderten tek uç.
    _rate_limit("request-otp-ip", ip, limit=OTP_IP_LIMIT, window=OTP_IP_WINDOW)

    user = db.scalar(select(models.User).where(models.User.email == payload.email))
    if user is None:
        return {"detail": "Doğrulama kodu gönderildi."}
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
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """E-posta + şifre ile giriş (OTP'siz).

    HIZ LİMİTİ KOVASI (e-posta, IP) İKİLİSİYLE ANAHTARLANIR ve başarılı
    girişte SIFIRLANIR. İkisi de bir DoS'u kapatmak için:

    Kova yalnızca e-postayla anahtarlanıyor ve başarı onu temizlemiyorken,
    kurbanın adresini bilen herkes 5 yanlış şifre göndererek o hesabı 15
    dakika boyunca KENDİ DOĞRU ŞİFRESİYLE bile giremez hâle getiriyordu; her
    15 dakikada bir 5 istek tekrarlanarak kilit süresiz uzatılabiliyordu.
    Yani kaba kuvvete karşı konan önlem, hesabı ele geçirmenin değil
    kapatmanın aracına dönüşmüştü.

    Artık saldırgan yalnızca KENDİ IP'sinin kovasını doldurur; kurban başka
    bir adresten geldiği için etkilenmez, doğru şifreyle girdiği anda da kova
    tamamen sıfırlanır.

    KALAN RİSK, bilerek kabul edildi: farklı IP'lere sahip bir saldırgan
    hesap başına IP başına 5 deneme yapabilir. Şifreler scrypt ile
    saklandığı ve en az 8 karakter olduğu için bu, kurbanı süresiz kilitleme
    garantisinden daha küçük bir risk. Aynı NAT'ın (yurt/kampüs) arkasındaki
    biri hâlâ komşusunu kilitleyebilir — dağıtık sayaç (Redis) ve
    IP+hesap ayrımı bir sonraki adım.
    """
    ip = _client_ip(request)
    _rate_limit("login", payload.email, ip)
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

    # Başarılı giriş kovayı sıfırlar: kimliğini kanıtlayan kişinin, daha önceki
    # başarısız denemeler yüzünden bir sonraki girişte kilitlenmesi anlamsız.
    _reset_rate_limit("login", payload.email, ip)

    token = _issue_token(db, user)
    db.commit()
    return {"token": token, "user": user}


@router.post("/verify-otp", response_model=TokenOut)
def verify_otp(payload: VerifyIn, db: Session = Depends(get_db)):
    # 6 haneli kodun kaba kuvvetle denenmesini engeller (5 deneme / 15 dk).
    #
    # BURADA KOVA BİLEREK IP BOYUTU TAŞIMIYOR (login'in aksine). Sebebi
    # ödünleşimin ters yönde olması: IP eklenirsek her IP'ye ayrı 5 hak
    # doğar ve botnet'i olan biri 10^6'lık kod uzayını paralel tarayabilir —
    # yani kaba kuvvet gerçekten mümkün hâle gelir. Hesap başına tek sayaç
    # bunu kapatır; bedeli, kurbanın adresini bilen birinin OTP ile giriş
    # yolunu 15 dakika tıkayabilmesidir. Bu bir DoS ama TAM DEĞİL: şifreyle
    # giriş yolu açık kalır ve doğru kod girilince (aşağıda) kova sıfırlanır.
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
    if not _otp_matches(user.otp_hash, payload.code):
        raise HTTPException(status_code=400, detail="Kod hatalı.")

    user.verified = True
    user.otp_hash = None
    user.otp_expires = None

    # Doğru kodu bilen kişi kimliğini kanıtladı; kovayı sıfırla ki daha önceki
    # başarısız denemeler bir sonraki girişini engellemesin.
    _reset_rate_limit("verify-otp", payload.email)

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


def _delete_photo_files(urls: list[str]) -> int:
    """Kullanıcının yüklediği fotoğraf DOSYALARINI diskten siler.

    İşi app.uploads.delete_local_photos yapar; burada yalnızca çağrılır (o
    modül yalnızca UPLOADS_DIR içinde kalan ve BİZİM ürettiğimiz ad desenine
    uyan yolları siler, dış URL'leri atlar, yol geçişine kapalıdır).

    İMPORT NEDEN FONKSİYON İÇİNDE: app.uploads, app.auth'tan get_current_user
    alıyor. Modül seviyesinde import etmek döngü kurar.

    delete_local_photos yoksa sessizce 0 döner. Bu, hesap silmenin bir
    yardımcı fonksiyon eksikliği yüzünden 500 vermemesi içindir — dosya
    temizliği önemli ama hesabın silinmesi DAHA önemli.
    """
    if not urls:
        return 0
    try:
        from app.uploads import delete_local_photos
    except ImportError:  # pragma: no cover — uploads her zaman var
        return 0
    return delete_local_photos(urls)


def purge_user(db: Session, user: models.User) -> dict[str, int]:
    """Kullanıcıyı ve ona bağlı TÜM verileri siler. COMMIT ETMEZ.

    HESABI SİLEN İKİ UÇ DA BURAYI ÇAĞIRIR:
      - DELETE /api/auth/me          (kişinin kendisi, şifre doğrulamasıyla)
      - DELETE /api/admin/users/{id} (yönetici, gerekçe zorunlu)

    Ortak fonksiyon olması bir üslup tercihi değil: bu projede "silinecek
    satırlar" listesi elle iki yerde tutulsaydı, users.id'ye bakan yeni bir
    sütun eklendiğinde biri güncellenip diğeri unutulurdu. Aynı hata tek
    listeyle bile ÜÇ KEZ yaşandı (bkz. aşağıdaki reports.reporter_id notu ve
    tests/test_account_delete_references.py). Tek giriş noktası + şemadan
    türetilen süpürme, hatanın tekrarını yapısal olarak engelliyor.

    Dönen sözlük temizlenen satır sayılarıdır; yönetici ucu bunu yanıtında
    döndürüp "ne silindi" sorusunu cevaplar.
    """
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
    deleted_messages = 0
    if message_ids:
        deleted_messages = db.query(models.Message).filter(
            models.Message.id.in_(message_ids)
        ).delete(synchronize_session=False)
    deleted_matches = db.query(models.Match).filter(
        (models.Match.user_a_id == uid) | (models.Match.user_b_id == uid)
    ).delete(synchronize_session=False)

    listing_ids = [
        l.id for l in db.query(models.Listing.id).filter_by(owner_id=uid)
    ]
    # Fotoğraf URL'leri satırlar silinmeden ÖNCE toplanır: silindikten sonra
    # hangi dosyaların bu kullanıcıya ait olduğunu söyleyecek hiçbir kayıt
    # kalmaz ve dosyalar /uploads/ altında sonsuza kadar erişilebilir durur.
    photo_urls: list[str] = list(user.photos or [])
    for row in db.query(models.Listing.photos).filter_by(owner_id=uid):
        photo_urls.extend(row.photos or [])

    deleted_swipes = 0
    if listing_ids:
        deleted_swipes += db.query(models.Swipe).filter(
            models.Swipe.listing_id.in_(listing_ids)
        ).delete(synchronize_session=False)
    deleted_swipes += db.query(models.Swipe).filter(
        models.Swipe.swiper_id == uid
    ).delete(synchronize_session=False)
    deleted_listings = db.query(models.Listing).filter_by(owner_id=uid).delete(
        synchronize_session=False
    )

    # Raporlar: reporter_id users.id'ye yabancı anahtarla bağlı — temizlenmezse
    # Postgres kısıtı hesabın silinmesini engeller (SQLite'ta FK varsayılan
    # kapalı olduğu için bu sessizce gözden kaçabiliyordu).
    deleted_reports = db.query(models.Report).filter_by(reporter_id=uid).delete(
        synchronize_session=False
    )
    # Hedefi bu kullanıcı olan raporlar da silinir. target_id'de yabancı anahtar
    # YOK, yani teknik bir zorunluluk değil; karar şu gerekçeyle verildi:
    # inceleme konusu içerik artık yok, rapor açıldığında hedefi bulunamıyor.
    # Temizlenmezse yönetici kuyruğunda var olmayan bir kullanıcıyı/ilanı/mesajı
    # gösteren, tıklanınca 404 veren ölü kayıtlar birikir. Aynı gerekçeyle
    # kullanıcının silinen ilan ve mesajlarına açılmış raporlar da temizlenir.
    deleted_reports += db.query(models.Report).filter(
        models.Report.target_type == "user", models.Report.target_id == uid
    ).delete(synchronize_session=False)
    if listing_ids:
        deleted_reports += db.query(models.Report).filter(
            models.Report.target_type == "listing",
            models.Report.target_id.in_(listing_ids),
        ).delete(synchronize_session=False)
    if message_ids:
        deleted_reports += db.query(models.Report).filter(
            models.Report.target_type == "message",
            models.Report.target_id.in_(message_ids),
        ).delete(synchronize_session=False)

    db.query(models.AuthToken).filter_by(user_id=uid).delete(
        synchronize_session=False
    )

    # Son adım: kullanıcıya işaret eden nullable yabancı anahtarları boşalt.
    # Bunlar denetim izi alanlarıdır (kim askıya aldı / kim inceledi / kim
    # raporu kapattı / KİM KALICI SİLDİ) ve silinen kullanıcı BAŞKALARININ
    # satırlarında da geçebilir; temizlenmezse hesap hiç silinemez. Açık
    # silmelerden SONRA koşar, böylece zaten silinmiş satırlar boşuna
    # güncellenmez.
    #
    # models.AdminAction.actor_id de bu süpürmeye dahildir ve OLMASI GEREKEN
    # budur: yönetici hesabı silinince denetim kaydı aktörünü kaybeder ama
    # KENDİSİ DURUR. Kaydı aktörüyle birlikte silmek, "kim neyi neden sildi"
    # sorusunu silinen her yöneticiyle birlikte cevapsız bırakırdı — üstelik
    # izini silmenin en kolay yolu kendi hesabını silmek olurdu.
    for column in _nullable_user_fk_columns():
        db.execute(
            update(column.table).where(column == uid).values({column.name: None})
        )

    db.delete(user)
    db.flush()

    # SON ADIM: DİSKTEKİ FOTOĞRAFLAR.
    #
    # Bunlar silinmediğinde hesap silme sözü tutulmuş olmuyordu: arayüz
    # "hesabını silmek kalıcıdır, tamamen silinir" diyor, oysa /uploads/
    # girişsiz servis edildiği için kullanıcının yüzünün olduğu dosya, hesap
    # silindikten SONRA da URL'i bilen herkese 200 dönmeye devam ediyordu.
    # KVKK açısından bu bir silme talebinin yerine getirilmemesidir.
    #
    # İşlem sınırının DIŞINDA: dosya silme geri alınamaz, veritabanı ise bu
    # noktada henüz commit edilmedi. Çağıran rollback ederse dosyalar gitmiş,
    # satırlar durmuş olur (yetim URL). Bilinçli tercih: iki çağıran da
    # (DELETE /api/auth/me ve DELETE /api/admin/users/{id}) hemen ardından
    # commit ediyor ve buradan sonra hata verebilecek bir adım kalmıyor;
    # ters yönde hata yapmak — yani veri silinmiş görünürken fotoğrafın
    # yayında kalması — kullanıcı için çok daha ağır.
    deleted_photos = _delete_photo_files(photo_urls)

    return {
        "listings": deleted_listings,
        "matches": deleted_matches,
        "messages": deleted_messages,
        "swipes": deleted_swipes,
        "reports": deleted_reports,
        "photos": deleted_photos,
    }


@router.delete("/me", status_code=204)
def delete_account(
    payload: AccountDelete,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hesabı ve ona bağlı tüm verileri kalıcı olarak siler.

    Şifre doğrulaması BURADA yapılır, purge_user'da değil: yönetici ucu
    (DELETE /api/admin/users/{id}) başkasının şifresini bilemez, onun
    doğrulaması require_admin + gerekçe zorunluluğudur. Ortak olan yalnızca
    "hangi satırlar silinir" mantığıdır.
    """
    if not user.password_hash or not _verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=400, detail="Şifren hatalı.")

    purge_user(db, user)
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
