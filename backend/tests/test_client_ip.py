"""İstemci IP çözümü — X-Forwarded-For sahteciliğine karşı (güvenlik testi B1).

Vekil (Render) başlığı sona ekler; gerçek istemci EN SAĞDAKİ değerdir.
Saldırganın en sola yazdığı sahte IP, IP tabanlı hız limitlerini atlatmak için
kullanılamamalı. uvicorn --forwarded-allow-ips '*' request.client.host'u en
SOLDAKİ (sahte) değere ayarladığı için _client_ip ona GÜVENMEZ, ham başlığı
kendisi okur.
"""

from starlette.requests import Request

from app import auth, config


def _request(headers: list[tuple[str, str]], client=("10.0.0.1", 0)) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers]
    return Request({"type": "http", "headers": raw, "client": client})


def test_rightmost_xff_is_used_when_proxy_trusted(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", True)
    # Saldırgan en sola sahte IP yazar; Render gerçek IP'yi sona ekler.
    req = _request([("x-forwarded-for", "1.2.3.4, 203.0.113.9")])
    assert auth._client_ip(req) == "203.0.113.9"


def test_spoofed_leftmost_cannot_rotate_the_bucket(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", True)
    # Aynı gerçek istemci, her istekte farklı sahte sol değer: aynı IP dönmeli
    # (yoksa saldırgan her istekte yeni kovaya düşerek limiti atlardı).
    a = _request([("x-forwarded-for", "9.9.9.9, 203.0.113.9")])
    b = _request([("x-forwarded-for", "8.8.8.8, 203.0.113.9")])
    assert auth._client_ip(a) == auth._client_ip(b) == "203.0.113.9"


def test_multiple_xff_header_lines_take_last(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", True)
    # Vekil ayrı bir satır olarak ekleyebilir; en son satırın en sağı alınır.
    req = _request(
        [
            ("x-forwarded-for", "1.1.1.1"),
            ("x-forwarded-for", "203.0.113.9"),
        ]
    )
    assert auth._client_ip(req) == "203.0.113.9"


def test_socket_used_when_proxy_not_trusted(monkeypatch):
    monkeypatch.setattr(config, "TRUST_PROXY_HEADERS", False)
    # Vekile güvenilmiyorsa (doğrudan internet) başlık YOK SAYILIR, soket IP'si
    # kullanılır — aksi halde doğrudan kuruluma spoof edilebilir bir yol açılır.
    req = _request([("x-forwarded-for", "1.2.3.4")], client=("198.51.100.7", 0))
    assert auth._client_ip(req) == "198.51.100.7"
