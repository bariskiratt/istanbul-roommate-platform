"""İlan onayı: bir ilan yayına girmeden önce yöneticiden geçmeli mi?

Öğrenciler ilan açarken 3-6 fotoğraf yüklüyor. Metin otomatik denetimden
(app.moderation) geçiyor ama fotoğrafa bakan bir otomatik denetim yok: uygunsuz
bir görsel, başka sitelerden kopyalanmış ev fotoğrafı ya da üzerinde telefon
numarası yazan bir kare doğrudan desteye düşerdi. Bu modül bunun kapısıdır.

LISTING_REVIEW ortam değişkeni üç moddan birini seçer:

  all      VARSAYILAN. Her yeni ilan, her yeniden yayınlama ve yayındaki
           ilanın METNİNİN ya da FOTOĞRAFLARININ her değişikliği yönetici
           onayına düşer. Kira, oda sayısı, ev özellikleri gibi alanlar
           onaysız güncellenir: içerik riski taşımıyorlar.
  first    Güven modeli. Kullanıcının ilk ilanı onaya düşer; yöneticinin en az
           bir ilanını onayladığı (ve hiçbir ilanı kaldırılmamış) kişi
           sonrakileri beklemeden yayınlar. Hacim büyüyüp her ilana tek tek
           bakmak yetişemez olunca buna geçilir.
  flagged  Yalnızca dolandırıcılık kalıbı taşıyan metin (moderation.
           HOLD_FOR_REVIEW) onaya düşer. Bu modülden önceki davranış.

Her modda geçerli iki kural:
  * Dolandırıcılık kalıbı (IBAN, görmeden kapora) HER ZAMAN onaya düşer.
  * Yöneticinin kendi ilanı beklemez: onaylayacak kişi zaten kendisi.

Tanınmayan bir değer "all" sayılır: yanlış yazılmış bir ayarın cezası
fazladan bir onay adımıdır, denetimsiz yayın değil.

Onay bekleyen ilan için yöneticilere en fazla yarım saatte bir posta gider
(notify_admins); posta yalnızca sayıyı ve panelin adresini taşır.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Literal

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, emailer, models

Mode = Literal["all", "first", "flagged"]
MODES: tuple[Mode, ...] = ("all", "first", "flagged")
DEFAULT_MODE: Mode = "all"

# Yöneticiye giden "onay bekleyen ilan var" postasının en sık aralığı.
# Brevo'nun ücretsiz katmanı günde 300 posta; kayıt kodları da aynı kotadan
# yiyor. Bekleyen ilan sayısı postada yazdığı için sık posta bilgi de katmaz.
NOTICE_INTERVAL_SECONDS = 30 * 60

_notice_lock = threading.Lock()
_last_notice_at: float | None = None


def mode() -> Mode:
    """Geçerli onay modu. Her çağrıda ortamdan okunur (testler değiştirir)."""
    raw = os.getenv("LISTING_REVIEW", DEFAULT_MODE).strip().lower()
    return raw if raw in MODES else DEFAULT_MODE  # type: ignore[return-value]


def is_trusted(db: Session, user_id: int) -> bool:
    """Yönetici bu kişinin en az bir ilanını onayladı mı ("first" modu)?

    Kaldırılmış (moderation_removed) bir ilanı olan kişi güvenilir SAYILMAZ:
    bir kez onay alıp sonra kural dışı içerik koyan biri yöneticinin
    kararıyla tekrar onaylı yola döner.
    """
    removed = db.scalar(
        select(models.Listing.id)
        .where(
            models.Listing.owner_id == user_id,
            models.Listing.moderation_removed.is_(True),
        )
        .limit(1)
    )
    if removed is not None:
        return False
    approved = db.scalar(
        select(models.Listing.id)
        .where(
            models.Listing.owner_id == user_id,
            models.Listing.approved_at.is_not(None),
        )
        .limit(1)
    )
    return approved is not None


def requires_review(db: Session, user: models.User) -> bool:
    """Bu kişinin yayına girecek içeriği yönetici onayı beklemeli mi?

    Dolandırıcılık kalıbı bu fonksiyonun KONUSU DEĞİL; o, metne bakılarak
    moderation.holds_for_review ile ayrıca ve her modda uygulanır.
    """
    if user.is_admin:
        return False
    current = mode()
    if current == "all":
        return True
    if current == "first":
        return not is_trusted(db, user.id)
    return False


def notify_admins(background: BackgroundTasks, db: Session) -> None:
    """Yöneticilere "onay bekleyen ilan var" postasını sıraya koyar.

    Posta yanıt döndükten SONRA gider (BackgroundTasks): Brevo'nun yavaşlığı
    ilan açan öğrenciyi bekletmesin. En fazla NOTICE_INTERVAL_SECONDS'te bir;
    sayaç süreç başınadır (yeniden başlatma onu sıfırlar, bu en kötü ihtimalle
    fazladan bir posta demek).
    """
    global _last_notice_at
    recipients = sorted(config.ADMIN_EMAILS)
    if not recipients or not emailer.email_enabled():
        return
    now = time.monotonic()
    with _notice_lock:
        if (
            _last_notice_at is not None
            and now - _last_notice_at < NOTICE_INTERVAL_SECONDS
        ):
            return
        _last_notice_at = now
    pending = db.scalar(
        select(func.count())
        .select_from(models.Listing)
        .where(models.Listing.pending_review.is_(True))
    )
    background.add_task(emailer.send_review_notice, recipients, int(pending or 0))


def reset_notice_throttle() -> None:
    """Testler için: posta sayacını sıfırlar."""
    global _last_notice_at
    with _notice_lock:
        _last_notice_at = None
