"""Kira endeksi çarpanı testleri.

Çarpan, TÜİK bültenlerinden zincirlenerek bulunan bir çıpa (ANCHOR_FACTOR) ve
çıpadan sonraki aylık oranların çarpımıdır (bkz. app/indexing.py).
"""

import pytest

from app import indexing
from app.indexing import is_configured, rent_index


@pytest.fixture(autouse=True)
def _temiz_ortam(monkeypatch):
    monkeypatch.delenv("RENT_INDEX_FACTOR", raising=False)


def test_cipa_tuik_bultenlerinden_zincirlenen_degerle_ayni():
    """Çıpa, bültenlerdeki üç orandan yeniden hesaplanabilmeli.

    Sayı ileride elle değiştirilirse (ör. yanlış birim girilirse) bu test
    kaynağa dönmeye zorlar.
    """
    sub25_vs_ara24 = 1.0742   # Şubat 2025 bülteni
    haz25_vs_ara24 = 1.1667   # Haziran 2025 (Haziran 2026 bülteninin karşılaştırması)
    haz26_vs_haz25 = 1.3211   # Haziran 2026 bülteni

    beklenen = haz26_vs_haz25 * (haz25_vs_ara24 / sub25_vs_ara24)

    assert indexing.HEADLINE_FACTOR == pytest.approx(beklenen, abs=1e-5)


def test_servis_edilen_cipa_konut_bandinin_icinde():
    """Konut ana grubuna dayalı çıpa, türetilen sınırların dışına çıkmamalı.

    Sınırlar (bkz. app/indexing.py): konut Haziran 2026/Haziran 2025 = 1,4514
    çarpı Şubat→Haziran 2025 için 1,0861 (alt) … 1,1962 (üst).
    """
    konut_haz26_vs_haz25 = 1.4514
    alt = konut_haz26_vs_haz25 * 1.086111
    ust = konut_haz26_vs_haz25 * 1.0458**4

    assert alt < indexing.ANCHOR_FACTOR < ust
    # Manşet TÜFE her koşulda alt sınır: kira ondan hızlı arttı.
    assert indexing.ANCHOR_FACTOR > indexing.HEADLINE_FACTOR


def test_veri_donemi_ve_cipa_tutarli():
    assert indexing.DATA_PERIOD == "2025-02"
    assert indexing.ANCHOR_PERIOD > indexing.DATA_PERIOD


def test_cipadan_sonraki_aylar_carpilir(monkeypatch):
    monkeypatch.setattr(indexing, "ANCHOR_FACTOR", 1.5)
    monkeypatch.setattr(
        indexing, "MONTHLY_AFTER_ANCHOR", {"2026-07": 2.0, "2026-08": 1.0}
    )

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(1.5 * 1.02 * 1.01)
    assert indexed_to == "2026-08"


def test_cipadan_onceki_ay_yok_sayilir(monkeypatch):
    """Yanlışlıkla eski bir ay girilirse çarpana katılmamalı."""
    monkeypatch.setattr(indexing, "ANCHOR_FACTOR", 1.5)
    monkeypatch.setattr(indexing, "MONTHLY_AFTER_ANCHOR", {"2025-12": 99.0})

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(1.5)
    assert indexed_to == indexing.ANCHOR_PERIOD


def test_carpan_makul_bantta():
    """16 aylık Türkiye enflasyonu için 1.3-1.8 dışındaki değer birim hatasıdır.

    (ör. yüzdeyi çarpan sanıp 43.49 yazmak ya da tabloyu boş bırakmak.)
    """
    factor, _ = rent_index()
    assert 1.30 < factor < 1.80


def test_ortam_degiskeni_tabloyu_ezer(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "1.62")

    factor, indexed_to = rent_index()

    assert factor == 1.62
    assert indexed_to == "manuel"
    assert is_configured()


def test_bozuk_ortam_degiskeni_cipaya_duser(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "abc")

    factor, indexed_to = rent_index()

    assert factor == pytest.approx(indexing.ANCHOR_FACTOR)
    assert indexed_to == indexing.ANCHOR_PERIOD


def test_harita_fiyatlari_da_endekslenir():
    """Harita ve adil fiyat aynı fiyat düzeyinde konuşmalı.

    Endeksleme bir dönem yalnızca adil fiyat uçlarına uygulanıyordu: danışman
    bugünün lirasıyla konuşurken bütçe haritası veri dönemi (2025-02)
    fiyatlarını gösteriyor, yani kullanıcının bütçesini olduğundan yeterli
    gösteriyordu. Bu test o ayrışmanın geri gelmesini engeller.
    """
    from app.heatmap import index_market_prices

    geojson = {
        "features": [
            {"properties": {"avg_price": 20000.0}},
            {"properties": {"avg_price": None}},   # veri yok: dokunulmamalı
            {"properties": {}},                     # alan hiç yok
        ]
    }

    changed = index_market_prices(geojson, 1.5)

    assert changed == 1
    assert geojson["features"][0]["properties"]["avg_price"] == 30000
    assert geojson["features"][1]["properties"]["avg_price"] is None


def test_carpan_bir_ise_harita_fiyatlarina_dokunulmaz():
    from app.heatmap import index_market_prices

    geojson = {"features": [{"properties": {"avg_price": 20000.0}}]}

    assert index_market_prices(geojson, 1.0) == 0
    assert geojson["features"][0]["properties"]["avg_price"] == 20000.0
