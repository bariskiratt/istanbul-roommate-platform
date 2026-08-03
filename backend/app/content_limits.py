"""İçerik üreten uçlar için kullanıcı başına hız sınırı.

Hız sınırı yalnızca kimlik doğrulama uçlarında vardı (app.auth._rate_limit) ve
E-POSTA anahtarlıydı; giriş yapmış bir hesabın ilan, mesaj ya da rapor
üretmesine hiçbir sınır yoktu. Tek jetonla saniyeler içinde 80 ilan açılabiliyor
(bulgu H3), kuyruklar ve anonim liste ucu şişiyordu.

Neden auth._rate_limit yeniden kullanılmadı: oradaki sınır tüm uçlar için tek
bir sabittir (15 dakikada 5). Mesaj göndermeye uygulandığında normal bir sohbeti
kilitlerdi. Burada sınır UCA GÖRE ayarlanır ve anahtar kullanıcı kimliğidir.

Bellek-içi ve tek süreçlik: birden fazla işçi (worker) ile çalışan dağıtımda
her işçinin kendi sayacı olur, yani gerçek sınır işçi sayısıyla çarpılır. Kaba
suistimali durdurmak için yeterli; kesin kota isteniyorsa Redis vb. paylaşımlı
bir sayaç gerekir.
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

# Uç -> (pencere içindeki en fazla istek, pencere).
# Sınırlar NORMAL KULLANIMIN ÇOK ÜSTÜNDE seçildi: amaç kullanıcıyı yavaşlatmak
# değil, otomatik yığın üretimini durdurmak.
LIMITS: dict[str, tuple[int, timedelta]] = {
    # Gerçek bir kullanıcı saatte 20 ilan açmaz; taşınma sezonunda birkaç
    # ilan + düzenleme rahatlıkla sığar.
    "listing_create": (20, timedelta(hours=1)),
    # Sohbet hızlı olabilir: dakikada 30 mesaj hâlâ insan hızıdır.
    "message_send": (30, timedelta(minutes=1)),
    # Rapor: tekillik kısıtı zaten aynı hedefi tekrarlatmıyor; buradaki sınır
    # farklı hedefleri tarayarak kuyruk doldurmayı engeller.
    "report_create": (10, timedelta(hours=1)),
}

_BUCKETS: dict[tuple[str, int], list[datetime]] = {}


def check(action: str, user_id: int) -> None:
    """Sınır aşıldıysa 429 fırlatır; aşılmadıysa isteği sayar."""
    limit, window = LIMITS[action]
    now = datetime.now(timezone.utc)
    bucket = _BUCKETS.setdefault((action, user_id), [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        # En eski kayıt pencereden düşünce yeniden hak doğar.
        retry_after = max(1, int((window - (now - bucket[0])).total_seconds()))
        raise HTTPException(
            status_code=429,
            detail="Çok hızlı gidiyorsun. Biraz bekleyip tekrar dene.",
            headers={"Retry-After": str(retry_after)},
        )
    bucket.append(now)


def reset() -> None:
    """Sayaçları sıfırlar (testler; bkz. tests/conftest.py)."""
    _BUCKETS.clear()
