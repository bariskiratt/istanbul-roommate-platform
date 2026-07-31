"""E-posta alan adından üniversite tespiti.

Kayıt sırasında öğrencinin üniversitesi e-posta alan adından otomatik
doldurulur (ör. ali@itu.edu.tr -> İstanbul Teknik Üniversitesi). Alt alan
adları da eşleşir (ogr.iu.edu.tr, std.yildiz.edu.tr ...). Eşleşme yoksa None
döner ve alan boş kalır — kullanıcı profilden elle girebilir.
"""

# alan adı -> üniversite adı (İstanbul ağırlıklı + büyük şehir üniversiteleri)
DOMAINS: dict[str, str] = {
    # İstanbul — devlet
    "itu.edu.tr": "İstanbul Teknik Üniversitesi",
    "boun.edu.tr": "Boğaziçi Üniversitesi",
    "istanbul.edu.tr": "İstanbul Üniversitesi",
    "iuc.edu.tr": "İstanbul Üniversitesi-Cerrahpaşa",
    "marmara.edu.tr": "Marmara Üniversitesi",
    "yildiz.edu.tr": "Yıldız Teknik Üniversitesi",
    "msgsu.edu.tr": "Mimar Sinan Güzel Sanatlar Üniversitesi",
    "medeniyet.edu.tr": "İstanbul Medeniyet Üniversitesi",
    "tau.edu.tr": "Türk-Alman Üniversitesi",
    "sbu.edu.tr": "Sağlık Bilimleri Üniversitesi",
    # İstanbul — vakıf
    "ku.edu.tr": "Koç Üniversitesi",
    "sabanciuniv.edu": "Sabancı Üniversitesi",
    "gsu.edu.tr": "Galatasaray Üniversitesi",
    "bilgi.edu.tr": "İstanbul Bilgi Üniversitesi",
    "bau.edu.tr": "Bahçeşehir Üniversitesi",
    "khas.edu.tr": "Kadir Has Üniversitesi",
    "ozyegin.edu.tr": "Özyeğin Üniversitesi",
    "ozu.edu.tr": "Özyeğin Üniversitesi",
    "yeditepe.edu.tr": "Yeditepe Üniversitesi",
    "medipol.edu.tr": "İstanbul Medipol Üniversitesi",
    "aydin.edu.tr": "İstanbul Aydın Üniversitesi",
    "okan.edu.tr": "İstanbul Okan Üniversitesi",
    "isikun.edu.tr": "Işık Üniversitesi",
    "maltepe.edu.tr": "Maltepe Üniversitesi",
    "dogus.edu.tr": "Doğuş Üniversitesi",
    "gelisim.edu.tr": "İstanbul Gelişim Üniversitesi",
    "arel.edu.tr": "İstanbul Arel Üniversitesi",
    "ticaret.edu.tr": "İstanbul Ticaret Üniversitesi",
    "acibadem.edu.tr": "Acıbadem Üniversitesi",
    "bezmialem.edu.tr": "Bezmialem Vakıf Üniversitesi",
    "fsm.edu.tr": "Fatih Sultan Mehmet Vakıf Üniversitesi",
    "ihu.edu.tr": "İbn Haldun Üniversitesi",
    "uskudar.edu.tr": "Üsküdar Üniversitesi",
    "halic.edu.tr": "Haliç Üniversitesi",
    "iku.edu.tr": "İstanbul Kültür Üniversitesi",
    "beykent.edu.tr": "Beykent Üniversitesi",
    "nisantasi.edu.tr": "Nişantaşı Üniversitesi",
    "biruni.edu.tr": "Biruni Üniversitesi",
    "kent.edu.tr": "İstanbul Kent Üniversitesi",
    "topkapi.edu.tr": "İstanbul Topkapı Üniversitesi",
    # Büyük şehirler (İstanbul'a taşınan öğrenciler için)
    "metu.edu.tr": "ODTÜ",
    "odtu.edu.tr": "ODTÜ",
    "bilkent.edu.tr": "Bilkent Üniversitesi",
    "hacettepe.edu.tr": "Hacettepe Üniversitesi",
    "ankara.edu.tr": "Ankara Üniversitesi",
    "ege.edu.tr": "Ege Üniversitesi",
    "deu.edu.tr": "Dokuz Eylül Üniversitesi",
    "iyte.edu.tr": "İzmir Yüksek Teknoloji Enstitüsü",
    "uludag.edu.tr": "Bursa Uludağ Üniversitesi",
    "kocaeli.edu.tr": "Kocaeli Üniversitesi",
    "gtu.edu.tr": "Gebze Teknik Üniversitesi",
}


def university_from_email(email: str) -> str | None:
    """E-posta alan adını (alt alanlar dahil) bilinen üniversitelerle eşler."""
    domain = email.rsplit("@", 1)[-1].lower().strip()
    for known, name in DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return name
    return None
