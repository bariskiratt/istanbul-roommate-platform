"""Ortak test kurulumu."""

import pytest

from app import auth
from app import db as app_db  # noqa: F401 — SQLite FK dinleyicisini kurar

# NOT: "PRAGMA foreign_keys=ON" burada TEKRARLANMAZ. Dinleyici app/db.py
# içinde Engine sınıfına bağlıdır; bu modülü import etmek testlerin kurduğu
# motorlar için de yeterlidir. İkinci bir kopya tutulursa uygulama ile
# testler arasındaki ayar kaçınılmaz olarak birbirinden ayrışır.


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Bellek-içi hız limiti testler arasında taşınmasın."""
    auth._RATE_BUCKETS.clear()
    yield
    auth._RATE_BUCKETS.clear()


@pytest.fixture(autouse=True)
def _disable_moderation_ai(monkeypatch):
    """İçerik denetiminin yapay zeka katmanı testlerde kapalı kalsın.

    Geliştiricinin kabuğunda ANTHROPIC_API_KEY tanımlıysa testler ağa çıkar;
    sonuç hem yavaşlar hem de deterministik olmaz.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
