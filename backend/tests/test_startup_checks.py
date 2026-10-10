"""Açılış güvenlik denetimi testleri (app/startup_checks.py).

Kapsam:
  - is_production() DATABASE_URL'e bakar
  - ÜRETİMDE eksik MESSAGE_KEY / OTP_KEY / DEV_OTP=1 açılışı durdurur
  - Üretimde anahtarlar tamsa açılış geçer
  - Yerelde (DATABASE_URL yok) eksik anahtar yalnızca uyarıdır, durdurmaz
"""

import pytest

from app import auth, crypto, startup_checks


@pytest.fixture(autouse=True)
def _reset_key_caches():
    """Her test taze anahtar önbelleğiyle başlasın ve bitsin.

    crypto ve auth anahtarları süreç boyunca önbelleklenir; ortam değişkenini
    değiştiren bir test, önbelleği sıfırlamazsa sonraki testlere sızar.
    """
    def reset():
        crypto.reset_cache()
        auth._otp_key_loaded = False
        auth._otp_key = None

    reset()
    yield
    reset()


def _set_valid_keys(monkeypatch):
    # MESSAGE_KEY: >=32 karakterlik ham dize SHA-256 ile anahtara türetilir;
    # OTP_KEY: >=32 karakter yeterli. İkisi de app koduyla aynı kuralda.
    monkeypatch.setenv("MESSAGE_KEY", "r" * 40)
    monkeypatch.setenv("OTP_KEY", "s" * 40)


def test_is_production_follows_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert startup_checks.is_production() is False
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    assert startup_checks.is_production() is True


def test_local_without_keys_does_not_raise(monkeypatch):
    """Yerelde (üretim değil) eksik anahtar geliştirmeyi kırmamalı."""
    monkeypatch.delenv("MESSAGE_KEY", raising=False)
    monkeypatch.delenv("OTP_KEY", raising=False)
    monkeypatch.delenv("DEV_OTP", raising=False)
    # production açıkça False; hiçbir şey fırlatmamalı.
    startup_checks.check_startup_config(production=False)


def test_production_without_keys_refuses_to_boot(monkeypatch):
    monkeypatch.delenv("MESSAGE_KEY", raising=False)
    monkeypatch.delenv("OTP_KEY", raising=False)
    monkeypatch.delenv("DEV_OTP", raising=False)
    with pytest.raises(RuntimeError) as exc:
        startup_checks.check_startup_config(production=True)
    msg = str(exc.value)
    assert "MESSAGE_KEY" in msg
    assert "OTP_KEY" in msg


def test_production_with_keys_boots(monkeypatch):
    _set_valid_keys(monkeypatch)
    monkeypatch.delenv("DEV_OTP", raising=False)
    # Fırlatmamalı.
    startup_checks.check_startup_config(production=True)


def test_production_dev_otp_on_refuses_to_boot(monkeypatch):
    """DEV_OTP=1 üretimde şifresiz giriş kapısıdır — açılışı durdurur."""
    _set_valid_keys(monkeypatch)
    monkeypatch.setenv("DEV_OTP", "1")
    with pytest.raises(RuntimeError) as exc:
        startup_checks.check_startup_config(production=True)
    assert "DEV_OTP" in str(exc.value)


def test_production_dev_otp_on_only_warns_locally(monkeypatch):
    """Aynı tehlikeli ayar yerelde yalnızca günlüğe yazılır, durdurmaz."""
    _set_valid_keys(monkeypatch)
    monkeypatch.setenv("DEV_OTP", "1")
    startup_checks.check_startup_config(production=False)


def test_critical_problems_lists_each_issue(monkeypatch):
    monkeypatch.delenv("MESSAGE_KEY", raising=False)
    monkeypatch.delenv("OTP_KEY", raising=False)
    monkeypatch.setenv("DEV_OTP", "1")
    problems = startup_checks.critical_problems()
    assert len(problems) == 3
    joined = " ".join(problems)
    assert "MESSAGE_KEY" in joined and "OTP_KEY" in joined and "DEV_OTP" in joined
