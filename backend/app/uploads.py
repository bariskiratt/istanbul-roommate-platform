"""Fotoğraf yükleme ve fotoğraf URL politikası.

Dosyalar data/uploads/ altına rastgele adla yazılır ve /uploads/... yolundan
statik servis edilir. Dönen URL mutlaktır — ilan/profil fotoğrafı olarak
doğrudan <img src> içinde kullanılabilir.
Yayına alırken kalıcı depolama (S3 vb.) ve CDN düşünülmeli.

Bu modül ayrıca iki ORTAK yardımcıyı barındırır (diğer uçlar buradan çağırır):

  is_allowed_photo_url(url) -> bool   hangi fotoğraf adresleri kabul edilir
  delete_local_photos(urls) -> int    bizim ürettiğimiz dosyaları diskten siler

İkisi de tek bir soruya dayanır: "bu URL bizim ürettiğimiz bir dosya mı?"
Cevap dosya ADININ desenine bakılarak verilir (secrets.token_hex(16) + izinli
uzantı); böylece kullanıcının uydurduğu bir yol ("/uploads/../../etc/passwd")
ne kabul edilir ne de silinir.
"""

import os
import re
import secrets
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile

from app import models
from app.auth import get_current_user
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

MAX_BYTES = 5 * 1024 * 1024  # 5 MB

# İzin verilen içerik türü -> dosya uzantısı
ALLOWED = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Fotoğraf URL'si için üst sınır. Alan sınırsızken 2 MB'lık bir "data:" dizesi
# ilan fotoğrafı diye kaydedilebiliyordu (bulgu H2): satır şişiyor, anonim
# liste ucu megabaytlarca veri döndürüyordu.
MAX_PHOTO_URL_LENGTH = 500

# Statik montaj noktası (bkz. app/main.py: app.mount("/uploads", ...)).
UPLOADS_PREFIX = "/uploads/"

# Bizim ürettiğimiz dosya adı: secrets.token_hex(16) -> 32 onaltılık karakter.
_LOCAL_PHOTO_NAME = re.compile(r"[0-9a-f]{32}\.(?:jpg|png|webp)")

# Kendi yüklemelerimiz dışında kabul edilen barındırıcılar. Liste KAPALIDIR:
# demo/tohum verisi ve arayüzün varsayılan avatarları bunları kullanıyor,
# bunların dışındaki her adres reddedilir. Gerekçe: ilan fotoğrafı arayüzde
# <img src> olarak basılıyor; serbest bırakıldığında ilan sayfasını açan
# herkesin IP'si saldırganın sunucusuna düşer (izleme pikseli) ve ilanlar
# üçüncü tarafın istediği an değiştirebildiği içerikle doldurulabilir.
ALLOWED_PHOTO_HOSTS = frozenset(
    {
        "images.unsplash.com",
        "api.dicebear.com",
        "randomuser.me",
    }
)

# Dağıtıma özel ek barındırıcı (virgülle ayrılmış). Kendi CDN'ini bağlayan
# kurulum kaynağı değiştirmek zorunda kalmasın diye var; boş bırakılırsa
# yalnızca yukarıdaki kapalı liste geçerlidir.
EXTRA_PHOTO_HOSTS_ENV = "EXTRA_PHOTO_HOSTS"

# Dönen mutlak URL'nin tabanı. Tanımlıysa Host başlığı YOK SAYILIR (bulgu M4:
# "Host: evil.attacker.tld" gönderen istemci, veritabanına saldırganın
# alan adını taşıyan bir fotoğraf adresi yazdırabiliyordu). Tanımlı değilse
# istek adresine düşülür — tek makinelik geliştirme kurulumu böyle çalışır.
PUBLIC_BASE_URL_ENV = "PUBLIC_BASE_URL"


def _matches_signature(data: bytes, ext: str) -> bool:
    """İçerik, iddia edilen türün dosya imzasıyla uyuşuyor mu?"""
    if ext == "jpg":
        return data.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _extra_photo_hosts() -> set[str]:
    raw = os.getenv(EXTRA_PHOTO_HOSTS_ENV, "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _configured_host() -> str | None:
    """PUBLIC_BASE_URL'in alan adı (tanımlıysa)."""
    base = os.getenv(PUBLIC_BASE_URL_ENV, "").strip()
    if not base:
        return None
    return (urlparse(base).hostname or "").lower() or None


def public_base_url(request: Request) -> str:
    """Yüklenen dosyanın önüne konacak taban adres.

    PUBLIC_BASE_URL tanımlıysa o; değilse isteğin kendi adresi. Ortam
    değişkeni HER ÇAĞRIDA okunur — testler ve yeniden yapılandırma için.
    """
    configured = os.getenv(PUBLIC_BASE_URL_ENV, "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


def local_photo_name(url: str) -> str | None:
    """URL bizim ürettiğimiz bir dosyayı gösteriyorsa dosya adını verir.

    Alan adına BAKMAZ: dağıtım adresi değişse bile (dev'de localhost, yayında
    alan adı) eski kayıtlardaki dosyalar tanınmalı, yoksa hesap silmede
    diskte öksüz dosya kalır (bulgu H6). Alan adı denetimi kabul tarafında,
    is_allowed_photo_url içinde yapılır.

    Dosya adı deseni tam eşleşmedir; "/" ve ".." desene giremez, dolayısıyla
    yol geçişi (path traversal) burada zaten imkânsızdır.
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or len(url) > MAX_PHOTO_URL_LENGTH:
        return None
    parsed = urlparse(url)
    # Yalnızca göreli yol ya da http(s); "data:", "javascript:" vb. elenir.
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return None
    path = unquote(parsed.path)
    if not path.startswith(UPLOADS_PREFIX):
        return None
    name = path[len(UPLOADS_PREFIX):]
    if not _LOCAL_PHOTO_NAME.fullmatch(name):
        return None
    return name


def is_allowed_photo_url(url: str) -> bool:
    """Bu adres fotoğraf alanına yazılabilir mi?

    Kabul edilenler:
      1. Kendi /uploads/ yolumuz (göreli ya da mutlak). PUBLIC_BASE_URL
         tanımlıysa mutlak adresin alan adı da ona uymalıdır; aksi hâlde
         "https://evil.tld/uploads/<32 hex>.jpg" bizim dosyamız gibi görünürdü.
      2. Kapalı listedeki dış barındırıcılar — yalnız https.

    Başka her şey (data:, javascript:, rastgele alan adları, 500 karakteri
    aşan dizeler) reddedilir.
    """
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url or len(url) > MAX_PHOTO_URL_LENGTH:
        return False

    name = local_photo_name(url)
    if name is not None:
        host = (urlparse(url).hostname or "").lower()
        configured = _configured_host()
        if host and configured and host != configured:
            return False
        return True

    parsed = urlparse(url)
    # Dış barındırıcı yalnızca https: http olsaydı ilan sayfası karışık
    # içerik (mixed content) yüzünden zaten kırık görünürdü.
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return host in (ALLOWED_PHOTO_HOSTS | _extra_photo_hosts())


def delete_local_photos(urls: list[str]) -> int:
    """Verilen adreslerden BİZE AİT olanların dosyalarını siler.

    Dış barındırıcıdaki adresler (Unsplash vb.) ve tanımadığımız desendeki
    yollar atlanır. Silinen dosya sayısını döner.

    Neden gerekli: hesap/ilan silmede yalnızca veritabanı satırı siliniyordu;
    yüklenen fotoğraflar /uploads/ altında girişsiz ve kalıcı kalıyordu —
    "hesabın tamamen silinir" sözü tutulmuyordu (bulgu H6).

    Bu fonksiyon VERİTABANINA BAKMAZ: bir dosyanın başka bir kayıtta hâlâ
    kullanılıp kullanılmadığını ÇAĞIRAN taraf kontrol etmelidir
    (bkz. listings.purge_listing).
    """
    if not urls:
        return 0
    base = Path(UPLOADS_DIR).resolve()
    deleted = 0
    seen: set[str] = set()
    for url in urls:
        name = local_photo_name(url) if isinstance(url, str) else None
        if name is None or name in seen:
            continue
        seen.add(name)
        target = (base / name).resolve()
        # Kuşak kemer: desen zaten "/" içeremiyor, yine de sembolik bağ ya da
        # ileride gevşetilecek bir desen UPLOADS_DIR dışına çıkarmasın.
        if target.parent != base:
            continue
        try:
            target.unlink()
        except (FileNotFoundError, OSError):
            continue
        deleted += 1
    return deleted


@router.post("", status_code=201)
async def upload_photo(
    request: Request,
    file: UploadFile,
    _user: models.User = Depends(get_current_user),
):
    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise HTTPException(
            status_code=415,
            detail="Yalnızca JPEG, PNG veya WebP yüklenebilir.",
        )

    # Belleğe okumadan önce beyan edilen boyutu reddet (OOM önlemi)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES + 10_000:
        raise HTTPException(status_code=413, detail="Dosya 5 MB'den büyük olamaz.")

    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail="Dosya 5 MB'den büyük olamaz."
        )
    if not data:
        raise HTTPException(status_code=422, detail="Dosya boş.")
    if not _matches_signature(data, ext):
        raise HTTPException(
            status_code=415,
            detail="Dosya içeriği görüntü formatıyla uyuşmuyor.",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    (UPLOADS_DIR / name).write_bytes(data)

    return {"url": f"{public_base_url(request)}{UPLOADS_PREFIX}{name}"}
