"""E-posta -> üniversite eşlemesi ve heatmap 'lowdata' testleri."""

from app.heatmap import build_budget_heatmap, classify
from app.universities import university_from_email


def test_known_domains():
    assert university_from_email("ali@itu.edu.tr") == "İstanbul Teknik Üniversitesi"
    assert university_from_email("a@boun.edu.tr") == "Boğaziçi Üniversitesi"
    assert university_from_email("x@sabanciuniv.edu") == "Sabancı Üniversitesi"


def test_subdomains_match():
    assert university_from_email("ali@ogr.iu.edu.tr") == "İstanbul Üniversitesi"
    assert (
        university_from_email("ali@std.yildiz.edu.tr")
        == "Yıldız Teknik Üniversitesi"
    )
    assert university_from_email("a@ogrenci.marmara.edu.tr") == "Marmara Üniversitesi"


def test_alternate_domains():
    # Okulların kısaltma dışındaki tam alan adları da tanınmalı
    assert (
        university_from_email("huseyinilker.gocer@bahcesehir.edu.tr")
        == "Bahçeşehir Üniversitesi"
    )
    assert university_from_email("a@bau.edu.tr") == "Bahçeşehir Üniversitesi"


def test_unknown_domain_returns_none():
    assert university_from_email("ali@gmail.com") is None
    assert university_from_email("ali@bilinmeyen.edu.tr") is None


def test_register_sets_university(client=None):
    # client fixture'ı test_auth'taki gibi kurmak yerine hızlı birim testi:
    # kayıt ucunun davranışı auth testlerinde; burada saf fonksiyon yeter.
    assert university_from_email("BARIS@ITU.EDU.TR") == "İstanbul Teknik Üniversitesi"


def test_heatmap_lowdata_status():
    # 5 ilanlı mahalle bütçeye uygun bile olsa 'lowdata' işaretlenir
    assert classify(10000, 20000, listing_count=5) == "lowdata"
    assert classify(10000, 20000, listing_count=12) == "safe"
    assert classify(None, 20000, listing_count=None) == "nodata"

    result = build_budget_heatmap([10000, 10000, None], 20000, [5, 20, None])
    assert result["statuses"] == ["lowdata", "safe", "nodata"]
    assert result["summary"]["lowdata"] == 1
