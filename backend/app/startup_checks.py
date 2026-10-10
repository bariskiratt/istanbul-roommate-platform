"""Açılışta güvenlikle ilgili yapılandırmayı denetler ve günlüğe yazar.

Render'ın ücretsiz planında Shell yok; ortam değişkenlerinin doğru geldiğini
görmenin tek pratik yolu açılış günlükleridir. Bu modül her açılışta mesaj
şifreleme anahtarını, OTP anahtarını, DEV_OTP durumunu ve e-posta
yapılandırmasını tek blok hâlinde basar (bkz. DEPLOY.md §3).

Ayrıca ÜRETİMDE (DATABASE_URL tanımlı, yani Postgres'e bağlı gerçek dağıtım)
kritik bir sır eksik ya da tehlikeli bir ayar açıksa uygulamayı BAŞLATMAZ:

  * MESSAGE_KEY yok  -> mesajlar düz metin yazılır (app/crypto.py)
  * OTP_KEY yok      -> OTP kodları tuzsuz SHA-256; veritabanını gören 10^6
                        arama uzayında kodu geri bulup hesabı devralır
  * DEV_OTP=1        -> doğrulama kodu API yanıtında döner; şifresiz giriş
                        (ADMIN_EMAILS'teki bir adresle doğrudan yönetici olunur)

Bu üçü de "sessizce güvensiz çalışmak" yerine açılışta durur. Render başarısız
dağıtımda bir ÖNCEKİ sürümü sunmaya devam eder: yani kesinti olmaz, yalnızca
hatalı dağıtım görünür olur ve güvensiz hâl düzeltilene kadar hiç yayına çıkmaz.
Eski davranışta bu ayarlar yalnızca ilk mesaj/kod üretildiğinde tembel bir
uyarı basıyordu — üretimde fark edilmesi kolay değildi.

Yerelde ve CI'da DATABASE_URL tanımsızdır (SQLite'a düşülür, bkz. app/db.py);
orada eksik anahtar yalnızca uyarı olarak basılır, uygulama durmaz —
geliştirme kırılmaz.
"""

from __future__ import annotations

import os

from app import auth, crypto
from app.config import ADMIN_EMAILS, API_DOCS
from app.emailer import email_enabled


def is_production() -> bool:
    """Gerçek bir dağıtımda mıyız?

    Üretimde DATABASE_URL (Postgres) verilir; yerelde ve CI'da tanımsızdır ve
    SQLite'a düşülür (bkz. app/db.py). Sır zorunluluğu YALNIZCA üretimde
    uygulanır, böylece yerel geliştirme anahtarsız çalışmaya devam eder.
    """
    return bool(os.getenv("DATABASE_URL", "").strip())


def _dev_otp_enabled() -> bool:
    # auth._dev_otp_enabled() ile aynı kural; özel bir sembole bağlanmamak için
    # burada tekrar okunur (değer tek satırlık ve anlamı sabit).
    return os.getenv("DEV_OTP", "0") == "1"


def critical_problems() -> list[str]:
    """Üretimde açılışı engellemesi gereken kritik ayar sorunları.

    Ortamdan bağımsız hesaplanır; üretim kapısını `check_startup_config` uygular.
    """
    problems: list[str] = []
    if not crypto.key_available():
        problems.append(
            "MESSAGE_KEY yok ya da geçersiz — mesajlar düz metin saklanır"
        )
    if not auth.otp_key_available():
        problems.append(
            "OTP_KEY yok ya da geçersiz — OTP kodları tuzsuz SHA-256 ile saklanır"
        )
    if _dev_otp_enabled():
        problems.append(
            "DEV_OTP=1 — doğrulama kodu API yanıtında dönüyor (şifresiz giriş kapısı)"
        )
    return problems


def _mark(ok: bool, good: str, bad: str, *, warn_only: bool = False) -> str:
    """Tek bir durum satırı: sağlamsa ✅, değilse ❌ (uyarıysa ⚠️)."""
    if ok:
        return f"✅ {good}"
    return f"{'⚠️ ' if warn_only else '❌'} {bad}"


def summary_lines(*, production: bool) -> list[str]:
    """Her açılışta basılan güvenlik yapılandırması özeti (insan için)."""
    lines = [
        _mark(
            crypto.key_available(),
            "Mesaj şifreleme açık (MESSAGE_KEY geçerli)",
            "MESSAGE_KEY yok/geçersiz — mesajlar DÜZ METİN saklanacak",
        ),
        _mark(
            auth.otp_key_available(),
            "OTP kodları HMAC ile saklanıyor (OTP_KEY geçerli)",
            "OTP_KEY yok/geçersiz — kodlar tuzsuz SHA-256 (10^6 arama uzayı)",
        ),
        _mark(
            not _dev_otp_enabled(),
            "DEV_OTP kapalı (kod API yanıtında dönmüyor)",
            "DEV_OTP=1 — doğrulama kodu API yanıtında dönüyor",
        ),
        _mark(
            email_enabled(),
            "E-posta gönderimi yapılandırıldı (Brevo)",
            "E-posta yapılandırılmadı (BREVO_API_KEY/EMAIL_FROM) — kod yollanamaz",
            warn_only=True,
        ),
    ]
    # Bilgilendirici satırlar (başlı başına sorun değil).
    lines.append(f"ℹ️  Yönetici (ADMIN_EMAILS): {len(ADMIN_EMAILS)} adres tanımlı")
    if API_DOCS:
        lines.append("⚠️  API_DOCS=1 — /docs açık (yayında kapalı olmalı)")
    lines.append(
        "ℹ️  Ortam: "
        + ("üretim (DATABASE_URL var)" if production else "yerel/geliştirme (SQLite)")
    )
    return lines


def check_startup_config(*, production: bool | None = None) -> None:
    """Güvenlik yapılandırmasını günlüğe yazar; üretimde güvensizse durur.

    `production` verilmezse `is_production()` ile belirlenir (test için açık
    parametre). Üretimde `critical_problems()` boş değilse RuntimeError fırlatır
    ve uygulama başlamaz.
    """
    if production is None:
        production = is_production()

    print("🔒 Güvenlik yapılandırması:", flush=True)
    for line in summary_lines(production=production):
        print(f"   {line}", flush=True)

    if production:
        problems = critical_problems()
        if problems:
            raise RuntimeError(
                "Üretimde güvenli olmayan yapılandırma — açılış durduruldu: "
                + "; ".join(problems)
                + ". Gerekli ortam değişkenlerini ayarla (bkz. DEPLOY.md §3). "
                "Render bu dağıtımı başarısız sayıp bir önceki sürümü sunmaya "
                "devam eder; güvensiz hâl yayına çıkmaz."
            )
