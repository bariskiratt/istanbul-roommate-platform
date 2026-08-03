"""Proje genelindeki dosya yolları.

Yollar `__file__` üzerinden çözülüyor; böylece betikler hangi dizinden
çalıştırılırsa çalıştırılsın veriyi buluyor (cwd'ye bağımlı değil).
"""

import os
from pathlib import Path

# app/config.py -> app/ -> proje kökü
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"

# Ham veri
LISTINGS_CSV = RAW_DIR / "istanbulApartmentForRent.csv"
NEIGHBORHOOD_GEOJSON = RAW_DIR / "mahalle_geojson.json"

# Üretilen veri
MARKET_VALUES_CSV = PROCESSED_DIR / "neighborhood_market_values.csv"

# Eğitilmiş model
MODEL_PATH = MODELS_DIR / "fair_price_model.joblib"

# Uygulama veritabanı (ilanlar; ileride kullanıcı/eşleşme/mesaj)
DB_PATH = DATA_DIR / "app.db"

# Yönetici hesaplar (virgülle ayrılmış e-postalar).
#
# Bu liste artık yalnızca "Evler" sekmesinin görünürlüğünü değil, TÜM
# moderasyon yetkisini belirler. Buradaki bir adresle giriş yapan hesap
# models.User.is_admin ile yönetici sayılır (ayrı bir rol sütunu ya da ikinci
# bir doğrulama adımı YOKTUR) ve require_admin'e bağlı her uca erişir:
#   GET  /api/reports                  ham bildirim listesi
#   GET  /api/admin/summary            kuyruk sayaçları
#   GET  /api/admin/reports            karar bağlamıyla bildirim kuyruğu
#   PATCH /api/admin/reports/{id}      bildirimi kapatma / yeniden açma
#   GET  /api/admin/users              kullanıcı listesi/araması (sayfalı;
#                                      e-posta yalnız askıdaki hesaplar için)
#   POST /api/admin/users/{id}/suspend   askıya alma, oturumlarını düşürme
#   POST /api/admin/users/{id}/unsuspend askıyı kaldırma
#   GET  /api/admin/flagged            işaretli ilan VE ÖZEL MESAJ metinleri
#   GET  /api/admin/flagged?status=removed  kaldırılmış içerik (metinleriyle)
#   POST /api/admin/flagged/{kind}/{id}/review  ilanı yayından kaldırma,
#                                      mesaj metnini sabitle örtme
#   POST /api/admin/{kind}/{id}/restore  kaldırılanı yayına geri alma
#   GET  /api/admin/listings           TÜM ilanlar (pasif ve kaldırılmış dâhil)
#   PATCH /api/admin/listings/{id}     BAŞKASININ ilanını düzenleme
#   POST /api/admin/listings/{id}/publish  ilanı yayına alma
#   GET  /api/admin/actions            denetim kaydı
#   -- GERİ ALINAMAZ (gerekçe zorunlu, denetim kaydına yazılır) --
#   DELETE /api/admin/listings/{id}    ilanı KALICI silme
#   DELETE /api/admin/users/{id}       hesabı KALICI silme
#
# Yöneticinin YAPAMADIKLARI da bilinçli kararlardır: kendini ya da başka bir
# yöneticiyi askıya alamaz/silemez (son yönetici kendini kilitlerse yönetim
# geri gelmez) ve BAŞKA BİR KULLANICI OLARAK GİRİŞ YAPAMAZ (kimliğe bürünme
# ucu yok; ayrıntı app/admin.py ilke 3b).
#
# RİSK: yetki tek başına e-posta eşleşmesine dayandığı için, bu adreslerden
# birinin hesabını ele geçiren kişi doğrudan moderatör olur. Artık yalnızca
# içeriği gizleyemez, KALICI SİLEBİLİR de — aşağıdaki iki madde bu yüzden
# eskisinden daha önemli. İki sonucu var:
#   1. Kendi dağıtımında ADMIN_EMAILS'i MUTLAKA kendi adreslerinle ez;
#      aşağıdaki varsayılanlar bu repoda açıkça yazılı.
#   2. DEV_OTP üretimde 0 olmalı. 1 iken /auth/request-otp doğrulama kodunu
#      API yanıtında döndürür; buradaki bir adres için kod isteyip
#      /auth/verify-otp'a vermek yeterlidir — şifre hiç gerekmez. Adres henüz
#      kayıtlı değilse saldırgan önce onunla kayıt olabilir. Ayrıntı: DEPLOY.md.
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv(
        "ADMIN_EMAILS", "bariskirat5@gmail.com,baris.kirat@std.yildiz.edu.tr"
    ).split(",")
    if e.strip()
}

# ÖĞRENCİ E-POSTASI ZORUNLULUĞU — ADMIN_EMAILS'İN İKİNCİ İŞLEVİ
#
# Ürün "yalnızca .edu.tr adresiyle girilir" diye pazarlanıyor (arayüzdeki
# güvenlik metinleri bunu bir güvence olarak sunuyor), ama bu kural uzun süre
# YALNIZCA tarayıcıdaki bir if'ti: API'ye doğrudan istek atan biri
# saldirgan@gmail.com ile kayıt olup hesabı doğrulayabiliyordu. Kural artık
# sunucuda, app/auth.py içindeki EmailIn doğrulayıcısında zorlanıyor
# (bkz. auth.is_student_email).
#
# MUAFİYET: yukarıdaki ADMIN_EMAILS adresleri kuraldan MUAFTIR. Sebebi
# pratik: yöneticinin adreslerinden biri gmail.com'dur ve kural muafiyetsiz
# uygulanırsa yönetici KENDİ HESABINI AÇAMAZ — moderasyon uçlarının tamamı
# is_admin'e, o da e-posta eşleşmesine bağlı olduğu için sistem yöneticisiz
# kalır.
#
# Muafiyetin sınırı: bu liste elle yazılan, dağıtımı yapan kişinin kontrol
# ettiği bir ortam değişkenidir; dışarıdan bir kullanıcı buraya giremez. Yani
# muafiyet "gmail'e izin" değil, "işletmecinin kendi adreslerine izin"dir.
# Kendi dağıtımında ADMIN_EMAILS'i ezerken bunu da hatırla: buraya yazdığın
# her adres öğrenci doğrulamasını da atlar.
#
# Öğrenci adresi sayılanlar (auth.is_student_email):
#   - alan adı "edu.tr" ya da ".edu.tr" ile biten her adres
#   - app/universities.py DOMAINS listesindeki alan adları ve alt alanları.
#     Bu ikinci kural sabancıuniv.edu gibi .edu.tr OLMAYAN ama tanınan Türk
#     üniversitesi alan adları içindir; o öğrencileri kapıda bırakmamak için.

# Ters vekil (reverse proxy) arkasında mıyız?
#
# Hız limiti artık IP boyutu da taşıyor. Doğrudan internete bakan bir sunucuda
# istemcinin IP'si request.client.host'tur. Render/Nginx gibi bir vekilin
# arkasındaysak orası HER İSTEKTE vekilin IP'sini gösterir; o zaman tüm
# dünya tek bir kovaya düşer ve IP limiti anlamsızlaşır.
#
# X-Forwarded-For KOŞULSUZ okunamaz: başlık istemci tarafından uydurulabilir,
# yani her istekte farklı bir değer göndererek IP limiti tamamen atlanır.
# Bu yüzden varsayılan KAPALI; yalnızca gerçekten vekil arkasındaysan ve o
# vekil başlığı kendisi yazıyorsa TRUST_PROXY_HEADERS=1 ver.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"

# Kullanıcı fotoğrafları (yerelde üretilir, git'e girmez).
# Yayında kalıcı disk bağlanan yolu UPLOADS_DIR env ile ver.
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", DATA_DIR / "uploads"))
