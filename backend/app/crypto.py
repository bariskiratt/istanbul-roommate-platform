"""Mesaj şifreleme (AES-256-GCM).

Mesajlar veritabanına şifreli yazılır, okunurken çözülür.

ÖNEMLİ: Bu şifreleme SUNUCUDA saklanan veriyi korur (at-rest) ve taşımada
HTTPS kullanılır. UÇTAN UCA ŞİFRELEME DEĞİLDİR — anahtar sunucuda
bulunduğu için sunucu mesajları teknik olarak çözebilir. Kullanıcıya
gösterilen hiçbir metinde "uçtan uca" denmemelidir.

Anahtar: MESSAGE_KEY ortam değişkeni. İki biçim kabul edilir:
  1. base64 kodlanmış tam 32 bayt (tercih edilen; --genkey bunu üretir)
  2. en az 32 karakterlik rastgele ham dize — anahtar SHA-256 ile türetilir.
     Bu ikinci yol, Render'ın `generateValue: true` ile ürettiği değerin
     sessizce reddedilip düz metne düşmesini önlemek için vardır.

Üretmek için:

    python -m app.crypto --genkey

Anahtar tanımlı değilse mesajlar düz metin yazılır ve başlangıçta bir kez
uyarı loglanır; böylece yerel geliştirme kırılmaz.

Biçim: "enc:v1:" + base64(nonce(12 bayt) + ciphertext+tag)
"enc:v1:" ile başlamayan değerler ESKİ DÜZ METİN kabul edilir ve olduğu
gibi döner — üretimde hâlihazırda düz metin mesajlar var, geriye dönük
uyum şart.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

PREFIX = "enc:v1:"
KEY_ENV = "MESSAGE_KEY"
KEY_BYTES = 32  # AES-256
NONCE_BYTES = 12  # GCM standart nonce uzunluğu
# base64(32 bayt) olmayan ham dizelerden anahtar türetmek için asgari uzunluk.
# Render'ın `generateValue` değeri bu eşiğin üstündedir; "test" gibi zayıf
# değerlerin sessizce anahtar olmasını engeller.
MIN_RAW_KEY_LENGTH = 32

# Çözülemeyen (bozuk ya da farklı anahtarla yazılmış) kayıt için dönen değer.
# Sohbetin tamamının 500 vermesindense tek mesaj okunamaz görünür.
#
# DİLDEN BAĞIMSIZ bir işarettir, kullanıcıya gösterilecek metin DEĞİLDİR:
# arayüz bu sabiti tanıyıp kendi dilinde bir karşılık basar (bkz. i18n).
# Değeri değiştirmek arayüzün çevirisini bozar.
UNREADABLE = "[unreadable]"

# Anahtar süreç boyunca önbelleklenir.
_key: bytes | None = None
_loaded = False
# Basılmış uyarı metinleri. Tek bir bayrak yerine küme tutulur: eskiden ilk
# uyarı basıldıktan sonra FARKLI uyarılar da yutuluyordu (ör. "MESSAGE_KEY yok"
# görülünce "mesaj çözülemedi" hiç loglanmıyordu).
_warned: set[str] = set()


def _warn_once(message: str) -> None:
    """Aynı uyarıyı bir kez basar; farklı uyarılar birbirini bastırmaz."""
    if message in _warned:
        return
    _warned.add(message)
    print(f"⚠️  {message}", flush=True)


def reset_cache() -> None:
    """Önbelleği temizler — testlerde ortam değişkeni değiştirmek için."""
    global _key, _loaded
    _key = None
    _loaded = False
    _warned.clear()


def generate_key() -> str:
    """Yeni bir anahtar üretir (base64 kodlanmış 32 bayt)."""
    return base64.b64encode(secrets.token_bytes(KEY_BYTES)).decode()


def _load_key() -> bytes | None:
    global _key, _loaded
    if _loaded:
        return _key
    _loaded = True

    raw = os.getenv(KEY_ENV, "").strip()
    if not raw:
        _warn_once(
            f"{KEY_ENV} tanımlı değil — mesajlar düz metin saklanacak. "
            f"Anahtar üretmek için: python -m app.crypto --genkey"
        )
        return None

    # 1) Tercih edilen biçim: base64 kodlanmış tam 32 bayt (--genkey böyle üretir).
    try:
        decoded = base64.b64decode(raw, validate=True)
    except Exception:  # noqa: BLE001 — bozuk anahtar uygulamayı düşürmemeli
        decoded = b""
    if len(decoded) == KEY_BYTES:
        _key = decoded
        return _key

    # 2) Rastgele üretilmiş ham dize (ör. Render'ın `generateValue: true` değeri)
    #    base64 olarak 32 bayta çözülmez — bu durumda dizeden anahtar TÜRETİLİR.
    #    Böylece blueprint ile gelen anahtar sessizce düz metne düşmez.
    #    Türetme SHA-256'dır; girdi zaten yüksek entropili rastgele bir dizedir,
    #    parola değildir. Kısa/zayıf değerler kabul edilmez.
    if len(raw) >= MIN_RAW_KEY_LENGTH:
        _key = hashlib.sha256(raw.encode()).digest()
        return _key

    _warn_once(
        f"{KEY_ENV} çok kısa ({len(raw)} karakter; en az {MIN_RAW_KEY_LENGTH} "
        f"gerekir) — düz metin kullanılacak. Anahtar üretmek için: "
        f"python -m app.crypto --genkey"
    )
    return None


def _cipher():
    """AESGCM nesnesi döner; anahtar veya kütüphane yoksa None."""
    key = _load_key()
    if key is None:
        return None
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:  # pragma: no cover — bağımlılık requirements'ta var
        _warn_once("cryptography kurulu değil — mesajlar düz metin saklanacak.")
        return None
    return AESGCM(key)


def key_available() -> bool:
    """Şifreleme etkin mi (anahtar + kütüphane hazır mı)."""
    return _cipher() is not None


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(PREFIX)


def encrypt(plaintext: str) -> str:
    """Metni şifreler. Anahtar yoksa metni olduğu gibi döner."""
    if plaintext is None:
        return plaintext
    cipher = _cipher()
    if cipher is None:
        return plaintext
    nonce = os.urandom(NONCE_BYTES)
    blob = nonce + cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
    return PREFIX + base64.b64encode(blob).decode()


def decrypt(value: str | None) -> str | None:
    """Şifreli metni çözer.

    "enc:v1:" ile başlamayan eski düz metin satırlar olduğu gibi döner.
    Çözme başarısızsa UNREADABLE döner (istek 500 ile düşmez).
    """
    if not value or not value.startswith(PREFIX):
        return value

    cipher = _cipher()
    if cipher is None:
        _warn_once(
            f"Şifreli mesaj var ama {KEY_ENV} yok — içerik okunamıyor."
        )
        return UNREADABLE
    try:
        blob = base64.b64decode(value[len(PREFIX):], validate=True)
        nonce, payload = blob[:NONCE_BYTES], blob[NONCE_BYTES:]
        return cipher.decrypt(nonce, payload, None).decode("utf-8")
    except Exception:  # noqa: BLE001 — bozuk kayıt sohbeti kırmasın
        _warn_once("Bir mesaj çözülemedi (anahtar değişmiş olabilir).")
        return UNREADABLE


def _main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--genkey":
        print(generate_key())
        return 0
    print("Kullanım: python -m app.crypto --genkey")
    return 1


if __name__ == "__main__":  # pragma: no cover
    import sys

    raise SystemExit(_main(sys.argv))
