"""Kira endeksi çarpanı testleri.

Çarpan iki endeks seviyesinin oranıdır (bkz. app/indexing.py). Buradaki
testler hem oranın doğru hesaplandığını hem de tablo boşken ürünün SESSİZCE
eski fiyat düzeyini sunmadığını (indexed=False ile bildirdiğini) doğrular.
"""

import pytest

from app import indexing
from app.indexing import is_configured, rent_index


@pytest.fixture(autouse=True)
def _temiz_ortam(monkeypatch):
    monkeypatch.delenv("RENT_INDEX_FACTOR", raising=False)
    monkeypatch.setattr(indexing, "_warned", False)


def test_carpan_iki_endeks_seviyesinin_orani(monkeypatch):
    monkeypatch.setattr(
        indexing, "RENT_INDEX", {indexing.DATA_PERIOD: 200.0, "2026-07": 250.0}
    )

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(1.25)
    assert indexed_to == "2026-07"
    assert is_configured()


def test_en_guncel_ay_kullanilir(monkeypatch):
    monkeypatch.setattr(
        indexing,
        "RENT_INDEX",
        {indexing.DATA_PERIOD: 100.0, "2025-08": 130.0, "2026-07": 180.0},
    )

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(1.80)
    assert indexed_to == "2026-07"


def test_tablo_bosken_endeksleme_yapilmaz_ve_bildirilir(monkeypatch, capsys):
    """Yapılandırılmamışken çarpan 1.0 kalır ve durum görünür olur.

    Sessizce 1.0 dönmek, tahminleri aylarca eski fiyat düzeyinde bırakıp
    kullanıcıya doğruymuş gibi göstermek demekti.
    """
    monkeypatch.setattr(indexing, "RENT_INDEX", {})

    factor, indexed_to = rent_index()

    assert factor == 1.0
    assert indexed_to == indexing.DATA_PERIOD
    assert not is_configured()
    assert "endeksi yapılandırılmamış" in capsys.readouterr().out


def test_temel_donem_eksikse_endeksleme_yapilmaz(monkeypatch):
    """Tabloda güncel ay var ama DATA_PERIOD yoksa oran hesaplanamaz."""
    monkeypatch.setattr(indexing, "RENT_INDEX", {"2026-07": 250.0})

    factor, _ = rent_index()

    assert factor == 1.0
    assert not is_configured()


def test_ortam_degiskeni_tabloyu_ezer(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "1.5")

    factor, indexed_to = rent_index()

    assert factor == 1.5
    assert indexed_to == "manuel"
    assert is_configured()


def test_bozuk_ortam_degiskeni_tabloya_duser(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "abc")
    monkeypatch.setattr(
        indexing, "RENT_INDEX", {indexing.DATA_PERIOD: 100.0, "2026-07": 120.0}
    )

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(1.20)
    assert indexed_to == "2026-07"
