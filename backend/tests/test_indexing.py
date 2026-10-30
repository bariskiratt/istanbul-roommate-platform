"""Kira endeksi çarpanı testleri.

Çarpan, TCMB Yeni Kiracı Kira Endeksi'nin (İstanbul) yıllık değişiminden gelen
bir çıpa (ANCHOR_FACTOR) ve çıpadan sonraki aylık oranların çarpımıdır
(bkz. app/indexing.py).
"""

import pytest

from app import indexing
from app.indexing import is_configured, rent_index


@pytest.fixture(autouse=True)
def _temiz_ortam(monkeypatch):
    monkeypatch.delenv("RENT_INDEX_FACTOR", raising=False)


def test_cipa_ykke_istanbul_yillik_degisimi():
    """Çıpa, TCMB Şubat 2026 bültenindeki İstanbul YKKE yıllık değişimidir.

    Yıllık değişim Şubat 2025 → Şubat 2026'yı verir; bu yüzden çıpa ayı veri
    döneminin TAM 12 ay sonrası olmalı. Veri seti değişip DATA_PERIOD
    kayarsa bu test çıpanın da yeniden seçilmesini zorlar.
    """
    istanbul_subat26_yillik = 41.0   # TCMB YKKE bülteni, Şubat 2026

    assert indexing.ANCHOR_FACTOR == pytest.approx(1 + istanbul_subat26_yillik / 100)
    yil, ay = indexing.DATA_PERIOD.split("-")
    assert indexing.ANCHOR_PERIOD == f"{int(yil) + 1}-{ay}"


def test_aylik_oranlar_bulten_seviyeleriyle_tutarli():
    """Tablodaki aylık oranlar, bültenlerin endeks seviyelerine uymalı.

    TCMB YKKE İstanbul (2023=100): Temmuz 2026 309,4 · Eylül 2026 336,5.
    Temmuz seviyesinden Ağustos ve Eylül aylıklarıyla ilerlenince Eylül'e
    yuvarlama payı içinde varılmalı. Bir ay yanlış girilirse (ör. 4,9 yerine
    49 ya da Ankara'nın sayısı) bu test kırılır.
    """
    temmuz, eylul = 309.4, 336.5
    m = indexing.MONTHLY_AFTER_ANCHOR

    tahmin = temmuz * (1 + m["2026-08"] / 100) * (1 + m["2026-09"] / 100)

    assert tahmin == pytest.approx(eylul, rel=0.005)


def test_aylik_oranlar_aylik_gorunuyor():
    """Aylık oran yerine yıllık oran ya da endeks seviyesi girilmesin.

    İstanbul yeni kiracı kiraları ayda %0–5 arası hareket ediyor; %35,5
    (yıllık) ya da 336,5 (seviye) gibi bir değer yanlış sütundur.
    """
    for ay, oran in indexing.MONTHLY_AFTER_ANCHOR.items():
        assert -5 < oran < 10, f"{ay}: {oran} aylık oran gibi görünmüyor"


def test_kira_manset_tufenin_ustunde_artti():
    """Haziran 2026'ya kadar kira zinciri manşet TÜFE zincirinin üstünde.

    HEADLINE_FACTOR TÜİK bültenlerindeki üç orandan yeniden hesaplanır; sayı
    elle bozulursa bu test kaynağa dönmeye zorlar.
    """
    sub25_vs_ara24 = 1.0742   # Şubat 2025 bülteni
    haz25_vs_ara24 = 1.1667   # Haziran 2025 (Haziran 2026 bülteninin karşılaştırması)
    haz26_vs_haz25 = 1.3211   # Haziran 2026 bülteni
    assert indexing.HEADLINE_FACTOR == pytest.approx(
        haz26_vs_haz25 * (haz25_vs_ara24 / sub25_vs_ara24), abs=1e-5
    )

    kira = indexing.ANCHOR_FACTOR
    for ay, oran in indexing.MONTHLY_AFTER_ANCHOR.items():
        if ay <= "2026-06":
            kira *= 1 + oran / 100

    assert kira > indexing.HEADLINE_FACTOR


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
    """Veri döneminden bu yana ortalama aylık artış %0,5–5 arasında olmalı.

    Bunun dışı birim hatasıdır (ör. yüzdeyi çarpan sanıp 41.0 yazmak ya da
    aylık yerine yıllık oran girmek). Ay sayısına göre ölçeklendiği için her
    yeni bültenle elle genişletmek gerekmez.
    """
    factor, indexed_to = rent_index()

    def ay_no(donem: str) -> int:
        yil, ay = donem.split("-")
        return int(yil) * 12 + int(ay)

    aylar = ay_no(indexed_to) - ay_no(indexing.DATA_PERIOD)
    aylik = factor ** (1 / aylar) - 1

    assert 0.005 < aylik < 0.05


def test_ortam_degiskeni_tabloyu_ezer(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "1.62")

    factor, indexed_to = rent_index()

    assert factor == 1.62
    assert indexed_to == "manuel"
    assert is_configured()


def test_bozuk_ortam_degiskeni_tabloya_duser(monkeypatch):
    tablo = rent_index()
    monkeypatch.setenv("RENT_INDEX_FACTOR", "abc")

    assert rent_index() == tablo


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
