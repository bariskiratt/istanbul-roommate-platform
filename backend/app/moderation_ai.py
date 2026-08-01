"""İçerik denetimi — isteğe bağlı yapay zeka katmanı.

Yalnızca ANTHROPIC_API_KEY tanımlıysa devreye girer. Kural katmanının
kaçırdığı örtük ihlalleri (imalı taciz, kılık değiştirmiş dolandırıcılık)
yakalamak için kısa bir sınıflandırma istemi çalıştırır.

Bu katman hiçbir zaman kullanıcı akışını bloke etmez: zaman aşımı, ağ
hatası veya bozuk yanıt durumunda None döner ve çağıran taraf sessizce
kural tabanlı sonuca düşer.

Yeni bir HTTP kütüphanesi eklenmedi; proje zaten `requests` kullanıyor
(OTP e-postası için).
"""

from __future__ import annotations

import json
import os
import re

import requests

from app.moderation import (
    CINSEL,
    DOLANDIRICILIK,
    HAKARET,
    ILETISIM,
    KUFUR,
    NEFRET,
    SITE_DISI,
    TACIZ,
    Kind,
    ModerationResult,
)

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MODEL = "claude-haiku-4-5-20251001"

# Denetim istek içinde (senkron) çalışır; sağlayıcı yavaşladığında ilan
# oluşturmayı uzun süre kilitlememek için kısa tutulur.
TIMEOUT = 5

# Sınıflandırmaya gönderilen metnin üst sınırı (jeton maliyeti + gecikme).
MAX_INPUT_CHARS = 4000

MAX_TOKENS = 200

_ALLOWED_REASONS = frozenset(
    {KUFUR, HAKARET, NEFRET, CINSEL, TACIZ, DOLANDIRICILIK, SITE_DISI, ILETISIM}
)

_SYSTEM_PROMPT = (
    "Sen bir ev arkadaşı bulma platformunun içerik denetleyicisisin. "
    "Sana verilen metni değerlendir ve SADECE şu JSON'u döndür:\n"
    '{"action": "allow|flag|block", "reasons": ["..."]}\n\n'
    "reasons alanında yalnızca şu kodları kullan: "
    f"{', '.join(sorted(_ALLOWED_REASONS))}.\n\n"
    "block: küfür, hakaret, nefret söylemi, cinsel içerik, taciz/tehdit veya "
    "açık dolandırıcılık.\n"
    "flag: şüpheli ama kesin olmayan durumlar (örtük taciz, ısrarlı para "
    "talebi, site dışına çekme).\n"
    "allow: normal ilan veya sohbet metni.\n\n"
    "Kira, depozito, oda sayısı, semt, kurallar (sigara/evcil hayvan), "
    "cinsiyet tercihi gibi normal ilan bilgileri ihlal DEĞİLDİR. "
    "Sohbette telefon veya WhatsApp paylaşmak da normaldir. "
    "Açıklama yazma, sadece JSON döndür."
)

_KIND_LABEL = {"listing": "İLAN", "message": "SOHBET MESAJI"}

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def ai_enabled() -> bool:
    """Yapay zeka katmanı yapılandırılmış mı."""
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def classify(text: str, *, kind: Kind) -> ModerationResult | None:
    """Metni sınıflandırır. Katman kapalıysa veya hata olursa None döner."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or not text or not text.strip():
        return None

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": _SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Metin türü: {_KIND_LABEL.get(kind, kind)}\n"
                    "Değerlendirilecek metin:\n"
                    f"<metin>\n{text[:MAX_INPUT_CHARS]}\n</metin>"
                ),
            }
        ],
    }
    try:
        res = requests.post(
            API_URL,
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
                "content-type": "application/json",
            },
            timeout=TIMEOUT,
        )
        if res.status_code != 200:
            # Denetlenen metin loglanmaz; yalnız sağlayıcının hata sebebi.
            print(
                f"⚠️  Denetim modeli reddetti: HTTP {res.status_code} "
                f"{res.text[:200]}",
                flush=True,
            )
            return None
        return _parse(res.json())
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        print(
            f"⚠️  Denetim modeline ulaşılamadı: {type(exc).__name__}: {exc}",
            flush=True,
        )
        return None


def _parse(body: dict) -> ModerationResult | None:
    """API yanıtından {action, reasons} JSON'unu çıkarır."""
    text = ""
    for block in body.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text += block.get("text") or ""
    match = _JSON_RE.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    action = str(data.get("action", "allow")).strip().lower()
    if action not in ("allow", "flag", "block"):
        return None

    reasons: list[str] = []
    raw_reasons = data.get("reasons")
    if isinstance(raw_reasons, list):
        for item in raw_reasons[:8]:
            code = re.sub(r"[^a-z_]", "", str(item).strip().lower())[:40]
            if not code:
                continue
            # Modelin uydurduğu kodlar sözlüğe karışmasın: bilinmeyenler
            # "ai:" önekiyle saklanır.
            reason = code if code in _ALLOWED_REASONS else f"ai:{code}"
            if reason not in reasons:
                reasons.append(reason)

    score = {"allow": 0.0, "flag": 0.5, "block": 1.0}[action]
    if action != "allow" and not reasons:
        reasons = ["ai:belirtilmemis"]
    return ModerationResult(action=action, reasons=reasons, score=score)
