"""Fotoğraf yükleme, saklama ve fotoğraf URL politikası.

Dosyalar rastgele adla saklanır ve /uploads/<ad> yolundan bu modüldeki
serve_photo ucuyla servis edilir. Dönen URL mutlaktır — ilan/profil fotoğrafı
olarak doğrudan <img src> içinde kullanılabilir.

İki depo var, seçim S3_BUCKET ortam değişkeniyle yapılır:

  S3_BUCKET boş   -> konteyner diski (UPLOADS_DIR). Yerel geliştirme için.
                     Render'ın ücretsiz planında disk kalıcı DEĞİLDİR: her
                     yeniden dağıtımda ve servis uykuya her geçtiğinde
                     dosyalar silinir.
  S3_BUCKET dolu  -> S3 uyumlu kova (Cloudflare R2, AWS S3, Backblaze B2...).
                     Yayın için bu. Kurulum: DEPLOY.md §1.5.

URL iki depoda da AYNIDIR (api.evdes.tr/uploads/<ad>); fotoğraf baytları
kovadan bu sunucu üzerinden geçer. Böylece depo değişince ne veritabanındaki
adresler ne de arayüzün CSP'si (img-src) değişmek zorunda kalır.

Bu modül ayrıca iki ORTAK yardımcıyı barındırır (diğer uçlar buradan çağırır):

  is_allowed_photo_url(url) -> bool   hangi fotoğraf adresleri kabul edilir
  delete_local_photos(urls) -> int    bizim ürettiğimiz dosyaları depodan siler

("local" burada "diskte" değil "BİZİM ürettiğimiz" demektir; kova kullanılırken
de aynı isimler geçerlidir.)

İkisi de tek bir soruya dayanır: "bu URL bizim ürettiğimiz bir dosya mı?"
Cevap dosya ADININ desenine bakılarak verilir (secrets.token_hex(16) + izinli
uzantı); böylece kullanıcının uydurduğu bir yol ("/uploads/../../etc/passwd")
ne kabul edilir ne de silinir.
"""

import functools
import os
import re
import secrets
import threading
from pathlib import Path
from typing import NamedTuple
from urllib.parse import unquote, urlparse

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from app import content_limits, models
from app.auth import get_current_user
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

# /uploads/<ad> — fotoğrafın kendisi. Ayrı yönlendirici, çünkü yolu /api
# önekinin dışında (eski StaticFiles bağlamasıyla aynı adres).
files_router = APIRouter(tags=["uploads"])

MAX_BYTES = 5 * 1024 * 1024  # 5 MB

# İzin verilen içerik türü -> dosya uzantısı
ALLOWED = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
# Servis ederken ters yön: uzantı -> içerik türü
CONTENT_TYPES = {ext: ctype for ctype, ext in ALLOWED.items()}

# Tarayıcı fotoğrafı bir hafta önbellekte tutar. Dosya adı rastgele ve içerik
# hiç değişmez (aynı adla ikinci yazma yok), yani bayat kopya riski yoktur.
# "private": araya giren paylaşımlı önbellekler (CDN) SAKLAMASIN — hesap
# silinince fotoğrafın başkalarına servis edilmeye devam etmemesi için (H6).
PHOTO_CACHE_CONTROL = "private, max-age=604800, immutable"

# Fotoğraf URL'si için üst sınır. Alan sınırsızken 2 MB'lık bir "data:" dizesi
# ilan fotoğrafı diye kaydedilebiliyordu (bulgu H2): satır şişiyor, anonim
# liste ucu megabaytlarca veri döndürüyordu.
MAX_PHOTO_URL_LENGTH = 500

# Fotoğrafların servis edildiği yol (bkz. serve_photo). Kovada da nesne
# anahtarı bu önekle başlar: "uploads/<ad>".
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


# ---------------------------------------------------------------------------
# Depo: konteyner diski ya da S3 uyumlu kova
# ---------------------------------------------------------------------------


class BucketSettings(NamedTuple):
    bucket: str
    endpoint_url: str | None
    access_key_id: str | None
    secret_access_key: str | None
    region: str


def bucket_settings() -> BucketSettings | None:
    """Kova ayarları; S3_BUCKET boşsa None (disk kullanılır).

    Ortam değişkenleri HER ÇAĞRIDA okunur (PUBLIC_BASE_URL ile aynı gerekçe).
    Cloudflare R2 için:
      S3_BUCKET             kova adı
      S3_ENDPOINT_URL       https://<hesap-id>.r2.cloudflarestorage.com
      S3_ACCESS_KEY_ID      R2 API jetonunun erişim anahtarı
      S3_SECRET_ACCESS_KEY  R2 API jetonunun gizli anahtarı
      S3_REGION             boş bırak ("auto" — R2'nin beklediği değer)
    """
    bucket = os.getenv("S3_BUCKET", "").strip()
    if not bucket:
        return None
    return BucketSettings(
        bucket=bucket,
        endpoint_url=os.getenv("S3_ENDPOINT_URL", "").strip() or None,
        access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip() or None,
        secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", "").strip() or None,
        region=os.getenv("S3_REGION", "").strip() or "auto",
    )


@functools.lru_cache(maxsize=4)
def _s3_client(settings: BucketSettings):
    """Ayar başına tek istemci.

    İstemci iş parçacığı güvenlidir ama boto3'ün paylaşılan varsayılan
    oturumu DEĞİLDİR: açılıştaki kova sınaması ile ilk istek aynı anda istemci
    kurarsa ortak oturum bozulabilir. Bu yüzden her istemci kendi oturumundan.
    """
    return boto3.session.Session().client(
        "s3",
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        region_name=settings.region,
        config=BotoConfig(
            # Varsayılan 60 sn'lik bekleme, kova erişilemezken yükleme
            # isteğini dakikalarca asılı bırakırdı.
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 3, "mode": "standard"},
            # Yeni boto3 sürümleri her isteğe varsayılan olarak CRC
            # sağlama toplamı ekliyor; her S3 uyumlu sağlayıcı bunu
            # desteklemiyor. Yalnız zorunlu olduğunda gönderilsin.
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _object_key(name: str) -> str:
    return f"{UPLOADS_PREFIX.strip('/')}/{name}"


def _store_photo(name: str, data: bytes, content_type: str) -> None:
    """Dosyayı yapılandırılmış depoya yazar. Kova hatası yukarı fırlar."""
    settings = bucket_settings()
    if settings is None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / name).write_bytes(data)
        return
    _s3_client(settings).put_object(
        Bucket=settings.bucket,
        Key=_object_key(name),
        Body=data,
        ContentType=content_type,
        CacheControl=PHOTO_CACHE_CONTROL,
    )


def _is_missing(exc: ClientError) -> bool:
    code = str(exc.response.get("Error", {}).get("Code", ""))
    return code in {"NoSuchKey", "NotFound", "404"}


def bucket_available() -> bool:
    """Kova yapılandırılmış VE yazma/okuma/silme gerçekten çalışıyor mu?

    Açılışta report_photo_storage bunu çağırır ve sonucu loga yazar
    (DEPLOY.md §1.5). Shell'i olan bir kurulumda elle de çalıştırılabilir:

        python -c "from app import uploads; print(uploads.bucket_available())"

    False iki anlama gelir ve çıktı hangisi olduğunu söyler: S3_BUCKET hiç
    tanımlı değil (fotoğraflar hâlâ geçici diskte) ya da tanımlı ama anahtar,
    uç adresi veya kova adı yanlış.

    Sınama nesnesinin adı fotoğraf desenine UYMAZ; serve_photo onu asla
    servis etmez, yarıda kalırsa da hiçbir kayıt ona işaret etmez.
    """
    settings = bucket_settings()
    if settings is None:
        print("S3_BUCKET tanımlı değil: fotoğraflar konteyner diskinde.")
        return False
    client = _s3_client(settings)
    key = _object_key("_deploy-check")
    try:
        client.put_object(Bucket=settings.bucket, Key=key, Body=b"ok")
        body = client.get_object(Bucket=settings.bucket, Key=key)["Body"]
        try:
            ok = body.read() == b"ok"
        finally:
            body.close()
        client.delete_object(Bucket=settings.bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        print(f"Kovaya erişilemedi ({settings.bucket}): {exc}")
        return False
    return ok


def report_photo_storage() -> None:
    """Açılışta hangi deponun kullanıldığını, kovanın da çalışıp çalışmadığını
    loga yazar.

    Render'ın ücretsiz planında Shell yok; dağıtımdan sonra kovayı doğrulamanın
    tek yolu Logs sekmesindeki bu satırdır (DEPLOY.md §1.5). Sınama ağ isteği
    olduğu için ayrı iş parçacığında koşar: kova erişilemezken bile açılışı
    bekletmez.
    """
    settings = bucket_settings()
    if settings is None:
        print("⚠️  Fotoğraflar konteyner diskinde — Render'ın ücretsiz planında "
              "yeniden dağıtımda ve uykuda silinir. Kalıcı depo: DEPLOY.md §1.5")
        return

    def check() -> None:
        if bucket_available():
            print(f"✅ Fotoğraf kovası çalışıyor: {settings.bucket}")
        else:
            print(f"❌ Fotoğraf kovasına yazılamıyor ({settings.bucket}) — "
                  f"yüklemeler 503 verecek. Ayarlar: DEPLOY.md §1.5")

    threading.Thread(target=check, name="photo-bucket-check", daemon=True).start()


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
    """Verilen adreslerden BİZE AİT olanların dosyalarını depodan siler.

    Dış barındırıcıdaki adresler (Unsplash vb.) ve tanımadığımız desendeki
    yollar atlanır. Silinen dosya sayısını döner. Kovada S3 silme isteği
    nesnenin var olup olmadığını söylemez; orada sayı, hatasız tamamlanan
    silme isteklerinin sayısıdır.

    Neden gerekli: hesap/ilan silmede yalnızca veritabanı satırı siliniyordu;
    yüklenen fotoğraflar /uploads/ altında girişsiz ve kalıcı kalıyordu —
    "hesabın tamamen silinir" sözü tutulmuyordu (bulgu H6).

    Bu fonksiyon VERİTABANINA BAKMAZ: bir dosyanın başka bir kayıtta hâlâ
    kullanılıp kullanılmadığını ÇAĞIRAN taraf kontrol etmelidir
    (bkz. listings.purge_listing).

    Hata FIRLATMAZ: çağıranlar hesap ve ilan silme uçlarıdır; kovaya o an
    ulaşılamıyor diye silme işleminin kendisi 500 vermemeli. Silinemeyen
    nesne loga yazılır.
    """
    names: list[str] = []
    for url in urls or []:
        name = local_photo_name(url) if isinstance(url, str) else None
        if name is not None and name not in names:
            names.append(name)
    if not names:
        return 0

    settings = bucket_settings()
    if settings is not None:
        client = _s3_client(settings)
        deleted = 0
        for name in names:
            try:
                client.delete_object(Bucket=settings.bucket, Key=_object_key(name))
            except (BotoCoreError, ClientError) as exc:
                print(f"⚠️  Fotoğraf kovadan silinemedi ({name}): {exc}")
                continue
            deleted += 1
        return deleted

    base = Path(UPLOADS_DIR).resolve()
    deleted = 0
    for name in names:
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
    user: models.User = Depends(get_current_user),
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

    # Kota doğrulamadan SONRA sayılır: reddedilen dosya hak yemesin, ama
    # depoya yazılacak her dosya sayılsın (bkz. content_limits.LIMITS).
    content_limits.check("photo_upload", user.id)

    name = f"{secrets.token_hex(16)}.{ext}"
    try:
        # Kovaya yazma bir ağ isteğidir; olay döngüsünü bekletmesin.
        await run_in_threadpool(_store_photo, name, data, file.content_type)
    except (BotoCoreError, ClientError) as exc:
        print(f"⚠️  Fotoğraf kovaya yazılamadı: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Fotoğraf şu an kaydedilemedi. Biraz sonra tekrar dene.",
        )

    return {"url": f"{public_base_url(request)}{UPLOADS_PREFIX}{name}"}


@files_router.api_route(
    UPLOADS_PREFIX + "{name}", methods=["GET", "HEAD"], include_in_schema=False
)
def serve_photo(name: str):
    """Fotoğrafı depodan servis eder. Giriş istemez (ilan fotoğrafları herkese
    açık ilanlarda görünüyor).

    Yalnızca BİZİM ürettiğimiz ad deseni servis edilir; başka her ad 404'tür.
    nosniff ve "Content-Disposition: attachment" başlıklarını main.py'deki
    SecurityHeadersMiddleware /uploads/ yolu için ekler (M4).

    Senkron fonksiyon: kova istemcisi engelleyici; FastAPI bunu iş parçacığı
    havuzunda çalıştırır.
    """
    if not _LOCAL_PHOTO_NAME.fullmatch(name):
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
    media_type = CONTENT_TYPES[name.rsplit(".", 1)[1]]
    headers = {"Cache-Control": PHOTO_CACHE_CONTROL}

    settings = bucket_settings()
    if settings is None:
        path = Path(UPLOADS_DIR) / name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
        return FileResponse(path, media_type=media_type, headers=headers)

    try:
        body = _s3_client(settings).get_object(
            Bucket=settings.bucket, Key=_object_key(name)
        )["Body"]
        try:
            data = body.read()
        finally:
            body.close()
    except ClientError as exc:
        if _is_missing(exc):
            raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı.")
        print(f"⚠️  Fotoğraf kovadan okunamadı ({name}): {exc}")
        raise HTTPException(status_code=502, detail="Fotoğraf şu an yüklenemedi.")
    except BotoCoreError as exc:
        print(f"⚠️  Fotoğraf kovadan okunamadı ({name}): {exc}")
        raise HTTPException(status_code=502, detail="Fotoğraf şu an yüklenemedi.")
    return Response(content=data, media_type=media_type, headers=headers)
