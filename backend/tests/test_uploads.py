"""Fotoğraf yükleme, servis ve silme testleri."""

import io
import os
from datetime import datetime, timedelta, timezone

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import content_limits
from app import uploads as uploads_module
from app.db import Base, get_db
from app.main import app

# 1x1 PNG (geçerli imza yeterli; içerik doğrulaması content-type üzerinden)
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1e2d0000000049454e44ae426082"
)


@pytest.fixture()
def session_factory(tmp_path, monkeypatch):
    # Testler gerçek uploads klasörüne yazmasın
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", tmp_path)

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _auth_headers(client, email="ali@uni.edu.tr"):
    res = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Sifre1234"},
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_upload_requires_auth(client):
    res = client.post(
        "/api/uploads", files={"file": ("a.png", PNG_BYTES, "image/png")}
    )
    assert res.status_code == 401


def test_upload_png_returns_absolute_url(client, tmp_path):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 201, res.text
    url = res.json()["url"]
    assert "/uploads/" in url and url.endswith(".png")
    # Dosya gerçekten yazıldı
    name = url.rsplit("/", 1)[-1]
    assert (tmp_path / name).read_bytes() == PNG_BYTES


def test_reject_wrong_type(client):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415


def test_reject_too_big(client, monkeypatch):
    monkeypatch.setattr(uploads_module, "MAX_BYTES", 10)
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 413


def test_reject_empty_file(client):
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", b"", "image/png")},
    )
    assert res.status_code == 422


# --------------------------------------------------------------------------
# Servis ve silme — konteyner diski
# --------------------------------------------------------------------------


def _upload(client, headers) -> str:
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 201, res.text
    return res.json()["url"]


def test_disk_photo_is_served_with_cache_headers(client):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    res = client.get(f"/uploads/{name}")
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == uploads_module.PHOTO_CACHE_CONTROL


def test_only_our_name_pattern_is_served(client, tmp_path):
    # Dizinde olsa bile desen dışındaki bir dosya servis edilmez.
    (tmp_path / "notes.txt").write_text("gizli")
    assert client.get("/uploads/notes.txt").status_code == 404
    assert client.get(f"/uploads/{'a' * 32}.png").status_code == 404


def test_delete_removes_our_files_and_skips_others(client, tmp_path):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    deleted = uploads_module.delete_local_photos(
        [url, url, "https://images.unsplash.com/x.jpg", "/uploads/../app.db"]
    )
    assert deleted == 1
    assert not (tmp_path / name).exists()
    assert client.get(f"/uploads/{name}").status_code == 404


def _delete_account(client, headers):
    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": "Sifre1234"}
    )
    assert res.status_code == 204, res.text


def test_account_deletion_keeps_photos_another_account_uses(client, tmp_path):
    """Bir hesabı silmek, başka bir hesabın kullandığı dosyayı silmemeli (H6).

    Eskiden hesap silme profilde ve ilanlarda geçen HER dosyayı siliyordu.
    B, A'nın fotoğraf adresini kendi profiline yazıp hesabını silince A'nın
    fotoğrafı 404 veriyordu: herkes başkasının fotoğrafını silebiliyordu.
    """
    ayse = _auth_headers(client, "ayse@uni.edu.tr")
    berk = _auth_headers(client, "berk@uni.edu.tr")
    url = _upload(client, ayse)
    name = url.rsplit("/", 1)[-1]
    for headers in (ayse, berk):
        res = client.patch("/api/auth/me", headers=headers, json={"photos": [url]})
        assert res.status_code == 200, res.text

    _delete_account(client, berk)
    assert client.get(f"/uploads/{name}").status_code == 200

    # Son kullanan da gidince dosya silinir.
    _delete_account(client, ayse)
    assert not (tmp_path / name).exists()


def test_account_deletion_keeps_a_photo_used_by_another_listing(client):
    ayse = _auth_headers(client, "ayse@uni.edu.tr")
    berk = _auth_headers(client, "berk@uni.edu.tr")
    shared = _upload(client, ayse)
    res = client.post(
        "/api/listings",
        headers=ayse,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de 2+1",
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": [shared, _upload(client, ayse), _upload(client, ayse)],
            "rent": 18000,
            "room_count": "2+1",
        },
    )
    assert res.status_code == 201, res.text
    res = client.patch("/api/auth/me", headers=berk, json={"photos": [shared]})
    assert res.status_code == 200, res.text

    _delete_account(client, berk)

    name = shared.rsplit("/", 1)[-1]
    assert client.get(f"/uploads/{name}").status_code == 200


def _name(url: str) -> str:
    return url.rsplit("/", 1)[-1]


def _create_listing(client, headers, photos) -> int:
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de 2+1",
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": photos,
            "rent": 18000,
            "room_count": "2+1",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_photo_removed_from_profile_is_deleted(client, tmp_path):
    ayse = _auth_headers(client, "ayse@uni.edu.tr")
    kept, dropped = _upload(client, ayse), _upload(client, ayse)
    res = client.patch("/api/auth/me", headers=ayse, json={"photos": [kept, dropped]})
    assert res.status_code == 200, res.text

    res = client.patch("/api/auth/me", headers=ayse, json={"photos": [kept]})
    assert res.status_code == 200, res.text

    assert (tmp_path / _name(kept)).exists()
    assert not (tmp_path / _name(dropped)).exists()


def test_photo_removed_from_listing_is_deleted_unless_used_elsewhere(client, tmp_path):
    ayse = _auth_headers(client, "ayse@uni.edu.tr")
    photos = [_upload(client, ayse) for _ in range(5)]
    listing = _create_listing(client, ayse, photos[:3])
    # photos[1] profilde de duruyor: ilandan çıkması dosyayı silmemeli.
    res = client.patch("/api/auth/me", headers=ayse, json={"photos": [photos[1]]})
    assert res.status_code == 200, res.text

    # photos[0] ve photos[1] çıkıyor, photos[3] ve photos[4] giriyor.
    res = client.patch(
        f"/api/listings/{listing}", headers=ayse, json={"photos": photos[2:]}
    )
    assert res.status_code == 200, res.text

    assert not (tmp_path / _name(photos[0])).exists()
    for kept in photos[1:]:
        assert (tmp_path / _name(kept)).exists()


def test_liked_photo_outlives_its_removal_until_the_like_is_answered(
    client, session_factory, tmp_path
):
    """Beğeniler ekranı yanıt verilene kadar beğenilen kareyi gösterir; ilan
    sahibi o fotoğrafı bu arada ilandan çıkarsa bile dosya silinmez."""
    ayse = _auth_headers(client, "ayse@uni.edu.tr")
    ali = _auth_headers(client, "ali@uni.edu.tr")
    photos = [_upload(client, ayse) for _ in range(4)]
    listing = _create_listing(client, ayse, photos[:3])
    res = client.post(
        "/api/swipes",
        headers=ali,
        json={
            "listing_id": listing,
            "direction": "like",
            "target": {"kind": "photo", "photo_index": 0},
        },
    )
    assert res.status_code == 200, res.text

    res = client.patch(
        f"/api/listings/{listing}", headers=ayse, json={"photos": photos[1:]}
    )
    assert res.status_code == 200, res.text
    assert (tmp_path / _name(photos[0])).exists()
    _age(tmp_path / _name(photos[0]))
    assert _sweep(session_factory) == 0

    # Yanıtlanan beğeni artık hiçbir ekranda görünmüyor: süpürme dosyayı toplar.
    [like] = client.get("/api/swipes/received", headers=ayse).json()
    res = client.post(
        f"/api/swipes/{like['swipe_id']}/respond", headers=ayse, json={"accept": False}
    )
    assert res.status_code == 200, res.text
    assert _sweep(session_factory) == 1
    assert not (tmp_path / _name(photos[0])).exists()


# --------------------------------------------------------------------------
# Hiç bağlanmamış dosyaların süpürülmesi (sweep_orphan_photos)
# --------------------------------------------------------------------------


def _age(path, days=8):
    """Dosyayı ORPHAN_GRACE'ten eski göster."""
    old = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    os.utime(path, (old, old))


def _sweep(session_factory) -> int:
    db = session_factory()
    try:
        return uploads_module.sweep_orphan_photos(db)
    finally:
        db.close()


def test_sweep_deletes_old_unattached_photos_only(client, session_factory, tmp_path):
    ayse = _auth_headers(client)
    attached = _upload(client, ayse)
    res = client.patch("/api/auth/me", headers=ayse, json={"photos": [attached]})
    assert res.status_code == 200, res.text
    abandoned = _upload(client, ayse)
    fresh = _upload(client, ayse)
    (tmp_path / "notes.txt").write_text("bizim dosyamız değil")
    for url in (attached, abandoned):
        _age(tmp_path / _name(url))
    _age(tmp_path / "notes.txt")

    assert _sweep(session_factory) == 1

    assert (tmp_path / _name(attached)).exists()
    assert not (tmp_path / _name(abandoned)).exists()
    # Yeni yüklenmiş dosya hâlâ bir formda bekliyor olabilir.
    assert (tmp_path / _name(fresh)).exists()
    assert (tmp_path / "notes.txt").exists()


def test_sweep_does_nothing_when_no_record_uses_a_photo(client, session_factory, tmp_path):
    """Boş (ya da yanlış) veritabanında her dosya sahipsiz görünür: silinmez."""
    url = _upload(client, _auth_headers(client))
    _age(tmp_path / _name(url))

    assert _sweep(session_factory) == 0
    assert (tmp_path / _name(url)).exists()


class _NoThread:
    started: list[str] = []

    def __init__(self, target, name, daemon):
        self.name = name

    def start(self):
        _NoThread.started.append(self.name)


@pytest.fixture()
def no_thread(monkeypatch):
    _NoThread.started = []
    monkeypatch.setattr(uploads_module.threading, "Thread", _NoThread)
    return _NoThread


def test_sweeper_starts_by_default(no_thread, monkeypatch):
    monkeypatch.delenv("PHOTO_SWEEP", raising=False)
    monkeypatch.delenv("S3_BUCKET", raising=False)
    uploads_module.start_orphan_sweeper()
    assert no_thread.started == ["photo-orphan-sweep"]


def test_sweeper_can_be_switched_off(no_thread, monkeypatch):
    monkeypatch.setenv("PHOTO_SWEEP", "0")
    uploads_module.start_orphan_sweeper()
    assert no_thread.started == []


# --------------------------------------------------------------------------
# Fotoğraf adresi politikası (is_allowed_photo_url)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "host", ["images.unsplash.com", "api.dicebear.com", "randomuser.me"]
)
def test_former_demo_hosts_are_rejected(host):
    # Demo verisi ve varsayılan avatarlar için açılmıştı; ikisi de kaldırıldı.
    assert not uploads_module.is_allowed_photo_url(f"https://{host}/x.jpg")


def test_extra_photo_hosts_are_the_only_outside_hosts(monkeypatch):
    monkeypatch.setenv("EXTRA_PHOTO_HOSTS", "cdn.example.org, Media.Example.net")

    assert uploads_module.is_allowed_photo_url("https://cdn.example.org/a.jpg")
    assert uploads_module.is_allowed_photo_url("https://media.example.net/a.jpg")
    # Dış barındırıcı yalnız https ile; listede olmayan hiçbir alan adı geçmez.
    assert not uploads_module.is_allowed_photo_url("http://cdn.example.org/a.jpg")
    assert not uploads_module.is_allowed_photo_url("https://example.com/a.jpg")


# --------------------------------------------------------------------------
# S3 uyumlu kova (Cloudflare R2) — S3_BUCKET tanımlıyken
# --------------------------------------------------------------------------


class FakeS3:
    """boto3 S3 istemcisinin bu modülün kullandığı beş çağrısı."""

    def __init__(self):
        self.objects: dict[tuple[str, str], dict] = {}
        self.fail_with: Exception | None = None
        # Gerçek kova sayfa başına 1000 anahtar döner; testler sayfalamayı
        # sınamak için küçültür.
        self.page_size = 1000

    def _check(self):
        if self.fail_with is not None:
            raise self.fail_with

    def put_object(self, Bucket, Key, Body, **kwargs):
        self._check()
        self.objects[(Bucket, Key)] = {
            "Body": Body,
            "LastModified": datetime.now(timezone.utc),
            **kwargs,
        }

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        self._check()
        keys = sorted(k for b, k in self.objects if b == Bucket and k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        page = keys[start:start + self.page_size]
        result = {
            "Contents": [
                {"Key": k, "LastModified": self.objects[(Bucket, k)]["LastModified"]}
                for k in page
            ],
            "IsTruncated": start + self.page_size < len(keys),
        }
        if result["IsTruncated"]:
            result["NextContinuationToken"] = str(start + self.page_size)
        return result

    def get_object(self, Bucket, Key):
        self._check()
        if (Bucket, Key) not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "yok"}}, "GetObject"
            )
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["Body"])}

    def delete_object(self, Bucket, Key):
        self._check()
        self.objects.pop((Bucket, Key), None)


@pytest.fixture()
def bucket(monkeypatch):
    fake = FakeS3()
    monkeypatch.setenv("S3_BUCKET", "roommatch-photos")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://hesap.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "anahtar")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "gizli")
    monkeypatch.setattr(uploads_module, "_s3_client", lambda settings: fake)
    return fake


def test_bucket_settings_follow_env(bucket, monkeypatch):
    settings = uploads_module.bucket_settings()
    assert settings.bucket == "roommatch-photos"
    assert settings.endpoint_url == "https://hesap.r2.cloudflarestorage.com"
    assert settings.region == "auto"

    monkeypatch.delenv("S3_BUCKET")
    assert uploads_module.bucket_settings() is None


def test_upload_goes_to_bucket_not_disk(client, bucket, tmp_path):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    # URL biçimi değişmez: arayüz ve veritabanı depodan habersiz.
    assert "/uploads/" in url
    stored = bucket.objects[("roommatch-photos", f"uploads/{name}")]
    assert stored["Body"] == PNG_BYTES
    assert stored["ContentType"] == "image/png"
    assert list(tmp_path.iterdir()) == []


def test_bucket_photo_is_served_with_hardening_headers(client, bucket):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]

    res = client.get(f"/uploads/{name}")
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["content-type"] == "image/png"
    assert res.headers["cache-control"] == uploads_module.PHOTO_CACHE_CONTROL
    # M4 başlıkları kovadan gelen yanıtta da var.
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"] == "attachment"


def test_missing_bucket_photo_is_404(client, bucket):
    assert client.get(f"/uploads/{'b' * 32}.jpg").status_code == 404


def test_bucket_outage_on_upload_is_503(client, bucket):
    headers = _auth_headers(client)
    bucket.fail_with = EndpointConnectionError(endpoint_url="https://r2.invalid")
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 503
    assert bucket.objects == {}


def test_bucket_outage_on_read_is_502(client, bucket):
    url = _upload(client, _auth_headers(client))
    name = url.rsplit("/", 1)[-1]
    bucket.fail_with = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "hayır"}}, "GetObject"
    )
    assert client.get(f"/uploads/{name}").status_code == 502


def test_bucket_delete_never_raises(client, bucket):
    url = _upload(client, _auth_headers(client))
    bucket.fail_with = EndpointConnectionError(endpoint_url="https://r2.invalid")
    # Hesap silme bu yüzden 500 vermemeli: hata yutulur, sayı 0 döner.
    assert uploads_module.delete_local_photos([url]) == 0


def test_account_deletion_removes_photos_from_bucket(client, bucket):
    headers = _auth_headers(client)
    photos = [_upload(client, headers) for _ in range(3)]
    res = client.post(
        "/api/listings",
        headers=headers,
        json={
            "type": "ev_ilani",
            "title": "Kadıköy'de 2+1",
            "description": "Moda'ya 5 dakika.",
            "district": "Kadıköy",
            "photos": photos,
            "rent": 18000,
            "room_count": "2+1",
        },
    )
    assert res.status_code == 201, res.text
    assert len(bucket.objects) == 3

    res = client.request(
        "DELETE", "/api/auth/me", headers=headers, json={"password": "Sifre1234"}
    )
    assert res.status_code == 204
    assert bucket.objects == {}


def test_daily_upload_quota(client, monkeypatch, tmp_path):
    """Kovadaki depolama ücretli; tek hesap sınırsız yükleyemesin."""
    monkeypatch.setitem(content_limits.LIMITS, "photo_upload", (2, timedelta(days=1)))
    headers = _auth_headers(client)
    _upload(client, headers)
    _upload(client, headers)

    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    )
    assert res.status_code == 429
    assert "retry-after" in res.headers
    assert len(list(tmp_path.iterdir())) == 2


def test_rejected_file_does_not_use_quota(client, monkeypatch):
    monkeypatch.setitem(content_limits.LIMITS, "photo_upload", (1, timedelta(days=1)))
    headers = _auth_headers(client)
    res = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 415
    _upload(client, headers)


# --------------------------------------------------------------------------
# Sahipsiz dosya süpürmesi — kova
# --------------------------------------------------------------------------


def test_sweep_pages_through_the_bucket(client, bucket, session_factory):
    bucket.page_size = 2
    headers = _auth_headers(client)
    attached = _upload(client, headers)
    res = client.patch("/api/auth/me", headers=headers, json={"photos": [attached]})
    assert res.status_code == 200, res.text
    abandoned = [_upload(client, headers) for _ in range(4)]
    fresh = _upload(client, headers)
    # Desene uymayan nesneye (ör. kova sınaması) hiç dokunulmaz.
    bucket.put_object(Bucket="roommatch-photos", Key="uploads/_deploy-check", Body=b"ok")
    old = datetime.now(timezone.utc) - timedelta(days=8)
    for (b, key), obj in bucket.objects.items():
        if not key.endswith(_name(fresh)):
            obj["LastModified"] = old

    assert _sweep(session_factory) == 4

    left = {key for _, key in bucket.objects}
    assert left == {
        f"uploads/{_name(attached)}",
        f"uploads/{_name(fresh)}",
        "uploads/_deploy-check",
    }


def test_sweep_survives_a_bucket_outage(client, bucket, session_factory):
    _upload(client, _auth_headers(client))
    bucket.fail_with = EndpointConnectionError(endpoint_url="https://r2.invalid")
    with pytest.raises(EndpointConnectionError):
        _sweep(session_factory)
    # Arka plandaki döngü bu hatayı yakalayıp loga yazar ve ertesi gün dener;
    # liste alınamadığı için hiçbir şey silinmemiştir.
    bucket.fail_with = None
    assert len(bucket.objects) == 1


def test_sweeper_never_runs_against_a_bucket_without_the_real_database(
    bucket, no_thread, monkeypatch
):
    """Yerel .env'e yayın kovasının anahtarlarını koyan bir geliştirici, boş
    SQLite'a bakan bir süpürmeyle yayındaki her fotoğrafı sildirmesin."""
    monkeypatch.delenv("PHOTO_SWEEP", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    uploads_module.start_orphan_sweeper()
    assert no_thread.started == []

    monkeypatch.setenv("DATABASE_URL", "postgresql://neon.example/db")
    uploads_module.start_orphan_sweeper()
    assert no_thread.started == ["photo-orphan-sweep"]
