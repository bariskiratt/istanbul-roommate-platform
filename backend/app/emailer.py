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

# Gönderen adı alan adıyla hizalı olmalı: "Falanca <noreply@evdes.tr>" gibi
# bir marka/alan uyuşmazlığı spam filtrelerinde olumsuz puan alır.
DEFAULT_SENDER_NAME = "evdes.tr"


def email_enabled() -> bool:
    return bool(os.getenv("BREVO_API_KEY") and os.getenv("EMAIL_FROM"))


# Yönetici girişinin ikinci adımında giden posta. Bu kod yalnızca DOĞRU
# ŞİFREYLE istenebildiği için "yok sayabilirsin" demek yanlış olurdu: yönetici
# bu postayı kendisi istemediyse şifresi başkasının elinde demektir.
ADMIN_LOGIN_NOTE = (
    "Bu kod, yönetici hesabına şifreyle giriş yapıldığı için gönderildi. "
    "Giriş yapan sen değilsen şifren başkasının elinde: hemen değiştir."
)
DEFAULT_NOTE = "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin."


def send_otp_email(to: str, code: str, *, admin_login: bool = False) -> bool:
    """Kodu e-postayla yollar; başarı durumunu döner (istisna fırlatmaz).

    admin_login=True yönetici girişinin ikinci adımıdır: konu ve not, kodu
    istemeyen yöneticiyi şifresinin sızdığı konusunda uyaracak şekilde değişir.
    """
    if not email_enabled():
        return False

    label = "Yönetici giriş kodun" if admin_login else "Giriş kodun"
    note = ADMIN_LOGIN_NOTE if admin_login else DEFAULT_NOTE
    sender_name = os.getenv("EMAIL_FROM_NAME", DEFAULT_SENDER_NAME)
    payload = {
        "sender": {"name": sender_name, "email": os.environ["EMAIL_FROM"]},
        "to": [{"email": to}],
        "subject": f"{label}: {code}",
        # Düz metin karşılığı olmayan (HTML-only) postalar spam puanı alır;
        # her iki gövde de gönderilir.
        "textContent": (
            f"{label}: {code}\n\n"
            "Kod 10 dakika geçerlidir.\n"
            f"{note}\n\n"
            "evdes.tr"
        ),
        "htmlContent": (
            "<div style='font-family:sans-serif;max-width:420px;margin:auto'>"
            "<h2 style='margin:0 0 16px'>evdes.tr</h2>"
            f"<p>{label}:</p>"
            f"<p style='font-size:32px;font-weight:bold;letter-spacing:6px'>{code}</p>"
            f"<p style='color:#666'>Kod 10 dakika geçerlidir. {note}</p>"
            "</div>"
        ),
        # Brevo istatistiklerinde işlemsel postaları ayırt etmek için.
        "tags": ["otp"],
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
        if res.status_code not in (200, 201):
            # Kod/alıcı loglanmaz; yalnız sağlayıcının hata sebebi.
            print(f"⚠️  Brevo gönderimi reddetti: HTTP {res.status_code} "
                  f"{res.text[:300]}", flush=True)
            return False
        return True
    except requests.RequestException as exc:
        print(f"⚠️  Brevo'ya ulaşılamadı: {type(exc).__name__}: {exc}", flush=True)
        return False
