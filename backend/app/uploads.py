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

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413, detail="Dosya 5 MB'den büyük olamaz."
        )
    if not data:
        raise HTTPException(status_code=422, detail="Dosya boş.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(16)}.{ext}"
    (UPLOADS_DIR / name).write_bytes(data)

    return {"url": f"{str(request.base_url).rstrip('/')}/uploads/{name}"}
