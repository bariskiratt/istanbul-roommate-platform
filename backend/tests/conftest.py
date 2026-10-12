"""Ortak test kurulumu."""

import os

# Yönetici listesi YALNIZCA ortam değişkeninden okunur (varsayılanı yok, bkz.
# app/config.py) ve modül yüklenirken bir kez hesaplanır. Bu yüzden değer
# app'ten herhangi bir şey import edilmeden ÖNCE, burada verilir. Sabit bir
# değer seçildi ki geliştiricinin kabuğundaki ADMIN_EMAILS testleri
# değiştirmesin. Biri bilerek öğrenci adresi DEĞİL: yöneticinin .edu.tr
# kuralından muaf olması da böylece sınanır.
os.environ["ADMIN_EMAILS"] = "yonetici@uni.edu.tr,yonetici2@gmail.com"

import pytest  # noqa: E402

from app import auth, content_limits  # noqa: E402
from app import db as app_db  # noqa: F401,E402 — SQLite FK dinleyicisini kurar

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

    Fotoğraf adresi app.uploads.is_allowed_photo_url ile doğrulanıyor: kendi
    yüklemelerimiz dışında yalnızca EXTRA_PHOTO_HOSTS'taki barındırıcılar geçer.
    Sınamalar RFC 2606'nın ayırdığı bu adı kullandığı için listeyi üretimde de
    gevşetmek yerine, dağıtıma özel ek barındırıcı değişkeni testlerde
    dolduruluyor.
    """
    monkeypatch.setenv("EXTRA_PHOTO_HOSTS", "example.com")


@pytest.fixture(autouse=True)
def _dev_otp(monkeypatch):
    """Testler doğrulama kodunu yanıttaki dev_code alanından okur.

    Kodun varsayılanı kapalı (DEV_OTP="0"), bu yüzden testler modu açıkça
    açar; varsayılanı sınayan test değişkeni kendisi siler. E-posta
    anahtarı da silinir: geliştiricinin kabuğunda tanımlıysa testler
    gerçek e-posta göndermesin.
    """
    monkeypatch.setenv("DEV_OTP", "1")
    monkeypatch.delenv("BREVO_API_KEY", raising=False)


@pytest.fixture(autouse=True)
def _disable_moderation_ai(monkeypatch):
    """İçerik denetiminin yapay zeka katmanı testlerde kapalı kalsın.

    Geliştiricinin kabuğunda ANTHROPIC_API_KEY tanımlıysa testler ağa çıkar;
    sonuç hem yavaşlar hem de deterministik olmaz.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
