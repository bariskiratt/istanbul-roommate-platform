"""OTP e-postası gönderimi (Brevo API).

BREVO_API_KEY ve EMAIL_FROM tanımlıysa gerçek e-posta gönderilir; değilse
gönderim atlanır ve auth katmanı DEV_OTP moduna göre davranır.

Brevo seçildi çünkü ücretsiz katmanında (300 e-posta/gün) alan adı
doğrulaması gerektirmeden, doğrulanmış bir gönderici adresiyle herhangi bir
alıcıya gönderim yapılabiliyor.
"""

import os

import requests

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
# Gönderim istek içinde (senkron) yapılır; sağlayıcı yavaşladığında kayıt
# ucunu uzun süre kilitlememek için kısa tutulur.
TIMEOUT = 6


def email_enabled() -> bool:
    return bool(os.getenv("BREVO_API_KEY") and os.getenv("EMAIL_FROM"))


def send_otp_email(to: str, code: str) -> bool:
    """Kodu e-postayla yollar; başarı durumunu döner (istisna fırlatmaz)."""
    if not email_enabled():
        return False

    payload = {
        "sender": {"name": "RoomMatch", "email": os.environ["EMAIL_FROM"]},
        "to": [{"email": to}],
        "subject": f"RoomMatch giriş kodun: {code}",
        "htmlContent": (
            "<div style='font-family:sans-serif;max-width:420px;margin:auto'>"
            "<h2>RoomMatch</h2>"
            "<p>Giriş kodun:</p>"
            f"<p style='font-size:32px;font-weight:bold;letter-spacing:6px'>{code}</p>"
            "<p style='color:#666'>Kod 10 dakika geçerlidir. Bu isteği sen"
            " yapmadıysan bu e-postayı yok sayabilirsin.</p>"
            "</div>"
        ),
    }
    try:
        res = requests.post(
            BREVO_URL,
            json=payload,
            headers={
                "api-key": os.environ["BREVO_API_KEY"],
                "content-type": "application/json",
            },
            timeout=TIMEOUT,
        )
        return res.status_code in (200, 201)
    except requests.RequestException:
        return False
