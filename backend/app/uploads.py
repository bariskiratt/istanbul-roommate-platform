"""Fotoğraf yükleme.

Dosyalar data/uploads/ altına rastgele adla yazılır ve /uploads/... yolundan
statik servis edilir. Dönen URL mutlaktır (istek adresinden türetilir) —
ilan/profil fotoğrafı olarak doğrudan <img src> içinde kullanılabilir.
Yayına alırken kalıcı depolama (S3 vb.) ve CDN düşünülmeli.
"""

import secrets

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


def _matches_signature(data: bytes, ext: str) -> bool:
    """İçerik, iddia edilen türün dosya imzasıyla uyuşuyor mu?"""
    if ext == "jpg":
        return data.startswith(b"\xff\xd8\xff")
    if ext == "png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


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

    return {"url": f"{str(request.base_url).rstrip('/')}/uploads/{name}"}
