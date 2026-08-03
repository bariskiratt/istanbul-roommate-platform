"""Ortak test kurulumu."""

import pytest

from app import auth, content_limits
from app import db as app_db  # noqa: F401 — SQLite FK dinleyicisini kurar

# NOT: "PRAGMA foreign_keys=ON" burada TEKRARLANMAZ. Dinleyici app/db.py
# içinde Engine sınıfına bağlıdır; bu modülü import etmek testlerin kurduğu
# motorlar için de yeterlidir. İkinci bir kopya tutulursa uygulama ile
# testler arasındaki ayar kaçınılmaz olarak birbirinden ayrışır.


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Bellek-içi hız limiti testler arasında taşınmasın."""
    auth._RATE_BUCKETS.clear()
    # İçerik uçlarının sayacı (app.content_limits) süreç ömrü boyunca yaşar;
    # temizlenmezse bir testte açılan ilanlar sonraki testin kotasını yerdi.
    content_limits.reset()
    yield
    auth._RATE_BUCKETS.clear()
    content_limits.reset()


@pytest.fixture(autouse=True)
def _allow_fixture_photo_host(monkeypatch):
    """Testlerdeki example.com fotoğraf adresleri kabul edilsin.

    Fotoğraf adresi artık kapalı bir listeye göre doğrulanıyor
    (app.uploads.is_allowed_photo_url) ve üretim listesinde example.com YOKTUR.
    Sınamalar RFC 2606'nın ayırdığı bu adı kullandığı için listeyi üretimde de
    gevşetmek yerine, dağıtıma özel ek barındırıcı değişkeni testlerde
    dolduruluyor.
    """
    monkeypatch.setenv("EXTRA_PHOTO_HOSTS", "example.com")


@pytest.fixture(autouse=True)
def _disable_moderation_ai(monkeypatch):
    """İçerik denetiminin yapay zeka katmanı testlerde kapalı kalsın.

    Geliştiricinin kabuğunda ANTHROPIC_API_KEY tanımlıysa testler ağa çıkar;
    sonuç hem yavaşlar hem de deterministik olmaz.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
