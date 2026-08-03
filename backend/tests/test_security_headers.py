"""Güvenlik başlıkları ve istek gövdesi üst sınırı testleri.

Kapsam:
  M5 — tüm yanıtlarda güvenlik başlıkları
  M4 — /uploads/ statik yanıtlarında nosniff + Content-Disposition
  H1 — Transfer-Encoding: chunked ile gövde boyutu sınırının atlanması
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app import uploads as uploads_module
from app.db import Base, get_db
from app.main import app

PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63f8ffff3f0005fe02fea72d1e2d0000000049454e44ae426082"
)


def _body_limit_middleware():
    """Kurulu ara katman yığınındaki gövde sınırı örneğini bulur.

    Sınır, yığın kurulurken (`MAX_REQUEST_BYTES`) örneğe KOPYALANIR; modül
    değişkenini yamalamak testte işe yaramaz, örneğin kendisi değiştirilmeli.
    """
    node = app.middleware_stack
    while node is not None:
        if isinstance(node, main_module.BodySizeLimitMiddleware):
            return node
        node = getattr(node, "app", None)
    raise AssertionError("BodySizeLimitMiddleware ara katman yığınında yok")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", tmp_path)

    # main.py, StaticFiles'ı import anında gerçek UPLOADS_DIR ile bağlıyor;
    # testin yazdığı dosyanın servis edilebilmesi için mount'u da yönlendir.
    for route in app.routes:
        if getattr(route, "name", None) == "uploads":
            monkeypatch.setattr(route.app, "directory", tmp_path)
            monkeypatch.setattr(route.app, "all_directories", [tmp_path])

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    # Ara katman yığını ilk istekte kurulur; _body_limit_middleware'in
    # çalışabilmesi için bir kez ısıtıyoruz.
    c.get("/api/legend")
    original = _body_limit_middleware().max_bytes
    yield c
    _body_limit_middleware().max_bytes = original
    app.dependency_overrides.clear()


def _token(client, email="ali@uni.edu.tr"):
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    return client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]


# --------------------------------------------------------------------------
# M5 — güvenlik başlıkları
# --------------------------------------------------------------------------


def test_security_headers_on_json_endpoint(client):
    res = client.get("/api/legend")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert res.headers["x-frame-options"] == "DENY"
    assert "geolocation=()" in res.headers["permissions-policy"]


def test_security_headers_on_error_response(client):
    """Hata yanıtları da korunmalı — 404/401 gövdeleri de tarayıcıya gider."""
    res = client.get("/api/bilinmeyen-uc")
    assert res.status_code == 404
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"


def test_no_hsts_over_plain_http(client):
    """HSTS düz http'de gönderilmemeli: yerel geliştirmeyi kilitler."""
    res = client.get("/api/legend")
    assert "strict-transport-security" not in res.headers


def test_hsts_over_https():
    """https istekte HSTS var ve `preload` İÇERMİYOR (geri alınamaz taahhüt)."""
    res = TestClient(app, base_url="https://testserver").get("/api/legend")
    hsts = res.headers["strict-transport-security"]
    assert "max-age=63072000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" not in hsts


@pytest.mark.parametrize(
    "proto,expected",
    [("https", True), ("https, http", True), ("http", False)],
)
def test_hsts_from_forwarded_proto(client, proto, expected):
    """Ters vekil TLS'i sonlandırıyorsa X-Forwarded-Proto yeter."""
    res = client.get("/api/legend", headers={"X-Forwarded-Proto": proto})
    assert ("strict-transport-security" in res.headers) is expected


def test_cors_headers_survive_security_middleware(client):
    """Güvenlik katmanı CORS başlıklarını ezmemeli (sıralama regresyonu)."""
    res = client.get("/api/legend", headers={"Origin": "http://localhost:5173"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert res.headers["x-frame-options"] == "DENY"


def test_cors_preflight_also_gets_security_headers(client):
    res = client.options(
        "/api/listings",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert res.headers["x-content-type-options"] == "nosniff"


def test_gzip_still_applies(client):
    """Sıkıştırma ara katmanı sıralama değişikliğinden sonra da çalışmalı."""
    res = client.get("/api/locations", headers={"Accept-Encoding": "gzip"})
    assert res.status_code == 200
    assert res.headers.get("content-encoding") == "gzip"
    assert res.headers["x-content-type-options"] == "nosniff"


# --------------------------------------------------------------------------
# M4 — /uploads/ statik yanıtları
# --------------------------------------------------------------------------


def test_uploaded_file_is_served_with_hardening_headers(client):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    url = client.post(
        "/api/uploads",
        headers=headers,
        files={"file": ("a.png", PNG_BYTES, "image/png")},
    ).json()["url"]
    name = url.rsplit("/", 1)[-1]

    res = client.get(f"/uploads/{name}")
    assert res.status_code == 200
    assert res.content == PNG_BYTES
    assert res.headers["x-content-type-options"] == "nosniff"
    # Belge olarak açılmasın (saklı XSS). <img src> etkilenmez: tarayıcı
    # Content-Disposition'ı yalnızca üst seviye gezinmede uygular.
    assert res.headers["content-disposition"] == "attachment"
    assert res.headers["cross-origin-resource-policy"] == "cross-origin"


def test_upload_headers_not_leaked_to_api_responses(client):
    """attachment YALNIZCA /uploads/ altında olmalı, JSON uçlarında değil."""
    res = client.get("/api/legend")
    assert "content-disposition" not in res.headers
    assert "cross-origin-resource-policy" not in res.headers


# --------------------------------------------------------------------------
# H1 — gövde üst sınırı
# --------------------------------------------------------------------------


def _chunks(total: int, size: int = 64 * 1024):
    """httpx'e üreteç verilince istek Transfer-Encoding: chunked gider."""
    sent = 0
    while sent < total:
        n = min(size, total - sent)
        yield b"x" * n
        sent += n


def _multipart_chunks(payload_bytes: int):
    """Biçimi geçerli, gövdesi devasa bir multipart akışı."""
    boundary = b"----roommatchtest"
    yield (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="a.png"\r\n'
        b"Content-Type: image/png\r\n\r\n"
    )
    yield PNG_BYTES
    yield from _chunks(payload_bytes)
    yield b"\r\n--" + boundary + b"--\r\n"


def test_declared_content_length_over_limit_is_rejected(client):
    """Content-Length bildirilmişse gövdeye hiç dokunulmadan 413."""
    _body_limit_middleware().max_bytes = 1024
    res = client.post("/api/listings", content=b"y" * 5000)
    assert res.status_code == 413
    assert "govdesi" in res.json()["detail"]


def test_chunked_body_over_limit_is_cut_off(client):
    """H1 kanıtı: Content-Length yokken de sınır uygulanıyor."""
    _body_limit_middleware().max_bytes = 256 * 1024
    res = client.post("/api/listings", content=_chunks(2 * 1024 * 1024))
    assert res.status_code == 413


def test_chunked_upload_over_limit_never_reaches_disk(client, tmp_path):
    """Chunked yükleme, dosya diske YAZILMADAN kesilmeli."""
    token = _token(client)
    _body_limit_middleware().max_bytes = 256 * 1024
    before = {p.name for p in tmp_path.iterdir()}
    res = client.post(
        "/api/uploads",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": (
                "multipart/form-data; boundary=----roommatchtest"
            ),
        },
        content=_multipart_chunks(2 * 1024 * 1024),
    )
    assert res.status_code == 413
    assert {p.name for p in tmp_path.iterdir()} == before


def test_chunked_body_under_limit_passes_through(client):
    """Sınırın altındaki chunked istek normal işlenmeli (yanlış pozitif yok)."""
    token = _token(client)
    payload = b'{"email":"ali@uni.edu.tr"}'
    res = client.post(
        "/api/auth/request-otp",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        content=iter([payload]),
    )
    # Uç ne dönerse dönsün, ÖNEMLİ olan 413 OLMAMASI.
    assert res.status_code != 413


def test_bodyless_methods_are_not_wrapped(client):
    """GET/HEAD/DELETE gövde sarmalayıcısına hiç girmemeli.

    Sınır 1 bayta çekilse bile gövdesiz yöntemler 413 almamalı. HEAD için kök
    adres kullanılır: FastAPI GET rotalarına HEAD'i kendiliğinden eklemez,
    yalnızca api_route ile açıkça bildirilen yollarda yanıt verir.
    """
    _body_limit_middleware().max_bytes = 1
    assert client.get("/api/legend").status_code == 200
    assert client.head("/").status_code == 200
    # DELETE gövdesizdir: kimlik doğrulamada takılır ama 413 ALMAZ.
    assert client.delete("/api/listings/1").status_code != 413
