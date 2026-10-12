"""Kullanıcıya dönen sunucu metinlerinin dili (Türkçe / İngilizce).

Arayüz İngilizce moddayken bile hata mesajları Türkçe geliyordu: arayüz
sunucunun `detail` metnini olduğu gibi gösteriyor, sunucu ise yalnızca Türkçe
biliyordu. Artık arayüz seçili dili her istekte `Accept-Language` başlığıyla
bildiriyor (frontend/src/lib/api.ts) ve sunucu metni o dilde üretiyor.

Nasıl çalışır:

* Türkçe KAYNAK dildir (arayüzdeki gibi). Kodda metinler Türkçe yazılır ve
  `localized("İlan bulunamadı.")` ile sarılır. İstek İngilizce ise karşılığı
  aşağıdaki `EN` sözlüğünden okunur; sözlükte yoksa Türkçe metin döner —
  eksik çeviri boş mesaj üretmez.
* Dil, isteğin başında `LanguageMiddleware` tarafından bir ContextVar'a
  yazılır; `localized` onu okur. Böylece dili uçtan uca parametre olarak
  taşımak gerekmez ve Pydantic doğrulayıcıları da (istek sırasında
  çalıştıkları için) aynı dili görür.
* Başlık yoksa ya da desteklenen bir dil içermiyorsa Türkçe kullanılır: API'yi
  doğrudan çağıranlar ve testler eskisi gibi Türkçe metin alır.

Yeni bir kullanıcı metni eklerken: `localized(...)` ile sar ve İngilizcesini
`EN`'e yaz. tests/test_i18n.py sarılmamış HTTPException metnini ve sözlükte
karşılığı olmayan `localized` çağrısını yakalar.
"""

import re
from contextvars import ContextVar

SUPPORTED_LANGS = ("tr", "en")
DEFAULT_LANG = "tr"

_lang: ContextVar[str] = ContextVar("lang", default=DEFAULT_LANG)

# Türkçe kaynak metin -> İngilizce karşılığı. {ad} yer tutucuları iki tarafta
# da aynı olmalı. Sayıya göre değişen metinlerde değer (tekil, çoğul)
# çiftidir; seçimi `n` değeri yapar.
EN: dict[str, str | tuple[str, str]] = {
    # ---- ortak ----
    "Giriş yapman gerekiyor.": "You need to sign in.",
    "İlan bulunamadı.": "Listing not found.",
    "Bütçe alt sınırı üst sınırdan büyük olamaz.":
        "The minimum budget can't be higher than the maximum.",
    "Fotoğraf adresi boş olamaz.": "Photo URL can't be empty.",
    "Fotoğraf adresi {max} karakterden uzun olamaz.":
        "Photo URL can't be longer than {max} characters.",
    "Fotoğraf adresi kabul edilmiyor: yalnızca uygulamaya yüklenen "
    "fotoğraflar ve izin verilen barındırıcılar geçerli.":
        "Photo URL not accepted: only photos uploaded to the app and "
        "allowed hosts are valid.",
    "Istek govdesi cok buyuk.": "Request body is too large.",

    # ---- kimlik doğrulama / hesap ----
    "Çok fazla deneme yapıldı. {unit} sonra tekrar dene.":
        "Too many attempts. Try again in {unit}.",
    "{n} dakika": ("{n} minute", "{n} minutes"),
    "{n} saat": ("{n} hour", "{n} hours"),
    "Hesabın yönetici tarafından askıya alındı.":
        "Your account has been suspended by an administrator.",
    "{detail} Sebep: {reason}": "{detail} Reason: {reason}",
    "Doğrulama e-postası gönderilemedi. Az sonra tekrar dene.":
        "The verification email couldn't be sent. Try again in a moment.",
    "Doğrulama kodu gönderildi.": "Verification code sent.",
    "Yalnızca üniversite e-posta adresiyle (.edu.tr) kayıt olunabilir. "
    "Okulunun sana verdiği adresi kullan.":
        "Only university email addresses (.edu.tr) can sign up. "
        "Use the address your school gave you.",
    "Geçerli bir e-posta adresi girin.": "Enter a valid email address.",
    "Yaş {min}-{max} aralığında olmalı.": "Age must be between {min} and {max}.",
    "Bölüm listeden seçilmelidir.": "Choose a department from the list.",
    "Bu e-posta zaten kayıtlı. Giriş yap.":
        "This email is already registered. Sign in instead.",
    "E-posta veya şifre hatalı.": "Incorrect email or password.",
    "Hesabın henüz doğrulanmamış. 'Kodla gir' ile e-postanı doğrula.":
        "Your account isn't verified yet. Sign in with a code to verify "
        "your email.",
    "Önce kod iste.": "Request a code first.",
    "Kodun süresi doldu. Yeni kod iste.":
        "Your code has expired. Request a new one.",
    "Kod hatalı.": "Incorrect code.",
    "Mevcut şifren hatalı.": "Your current password is incorrect.",
    "Yeni şifre eskisiyle aynı olamaz.":
        "The new password must be different from the old one.",
    "Şifren hatalı.": "Incorrect password.",
    "Yönetici hesabı: e-postana gelen kodu gir.":
        "Admin account: enter the code we just emailed you.",
    "Yönetici hesabı: kodla birlikte şifreni de gir.":
        "Admin account: enter your password along with the code.",
    "Çok hızlı gidiyorsun. Biraz bekleyip tekrar dene.":
        "You're going too fast. Wait a moment and try again.",

    # ---- ilanlar ----
    "Bu alanı düzenleyip tekrar deneyin.": "Edit this field and try again.",
    "Geçersiz özellik: {invalid}. Geçerli anahtarlar: {valid}.":
        "Invalid feature: {invalid}. Valid keys: {valid}.",
    "Ev ilanı için kira ve oda sayısı zorunlu.":
        "A room-offered listing needs a rent and a room count.",
    "Kişisel ilan için bütçe aralığı zorunlu.":
        "A looking-for-a-room listing needs a budget range.",
    "Yalnızca ev ilanları için hesaplanır.":
        "Only calculated for room-offered listings.",
    "Adil fiyat modeli yüklü değil.": "The fair price model isn't loaded.",
    "Bu ilan sana ait değil.": "This listing isn't yours.",

    # ---- harita / model ----
    "Veriler henüz yüklenmedi.": "Data hasn't loaded yet.",
    "Adil fiyat modeli yüklü değil. Önce 'python train_model.py' çalıştır.":
        "The fair price model isn't loaded. Run 'python train_model.py' first.",
    "Toplu taşıma verisi yüklü değil. Önce 'python -m scripts.fetch_transit' "
    "çalıştır.":
        "Transit data isn't loaded. Run 'python -m scripts.fetch_transit' first.",
    "Mahalle bulunamadı.": "Neighborhood not found.",
    "Bu mahalle raylı sisteme yürüme mesafesinde değil; ulaşım tabanlı öneri "
    "üretilemiyor.":
        "This neighborhood isn't within walking distance of the rail network, "
        "so no transit-based suggestions can be made.",

    # ---- beğeni / eşleşme / sohbet ----
    "Fotoğraf beğenisinde photo_index zorunlu.":
        "A photo like needs photo_index.",
    "Kart beğenisinde prompt_key zorunlu.": "A card like needs prompt_key.",
    "Hedef ve yorum yalnızca beğenide gönderilebilir.":
        "A target and a comment can only be sent with a like.",
    "Beğenilen fotoğraf bu ilanda yok.": "The liked photo isn't in this listing.",
    "Kendi ilanını kaydıramazsın.": "You can't swipe on your own listing.",
    "Beğeni bulunamadı.": "Like not found.",
    "Yorumunu düzenleyip tekrar gönder.": "Edit your comment and send it again.",
    "Eşleşme bulunamadı.": "Match not found.",
    "Bu hesap askıya alındı; şu an mesaj gönderilemiyor.":
        "This account is suspended, so messages can't be sent right now.",
    "Mesaj boş olamaz.": "Message can't be empty.",
    "Mesajını düzenleyip tekrar gönder.": "Edit your message and send it again.",

    # ---- içerik denetimi (moderation.describe) ----
    # Özneler cümlenin başında durur: "{subject} {labels} tespit edildi."
    "İçerikte": "This text",
    "Metinde": "The text",
    "Başlıkta": "The title",
    "Açıklamada": "The description",
    "Yorumda": "The comment",
    "{subject} {labels} tespit edildi.": "{subject} contains {labels}.",
    "{subject} topluluk kurallarımıza uymayan bir ifade tespit edildi.":
        "{subject} contains wording that goes against our community guidelines.",
    "küfür veya ağır hakaret": "profanity or a serious insult",
    "hakaret içeren ifade": "an insult",
    "nefret söylemi veya ayrımcılık": "hate speech or discrimination",
    "cinsel içerik": "sexual content",
    "taciz veya tehdit": "harassment or threats",
    "dolandırıcılık şüphesi taşıyan ifade": "wording that suggests a scam",
    "site dışına yönlendirme": "a push to move the conversation off the site",
    "iletişim bilgisi paylaşımı": "contact details",
    "Bu metin sistemin kendi kullandığı bir işaretle aynı; "
    "başka bir şey yazman gerekiyor.":
        "This text matches a marker the system uses itself; "
        "please write something else.",

    # ---- raporlar ----
    "Bu işlem için yönetici yetkisi gerekiyor.": "This action requires admin rights.",
    "Kendini raporlayamazsın.": "You can't report yourself.",
    "Raporlanacak içerik bulunamadı.": "The content to report wasn't found.",
    "Bu içeriği zaten raporladın.": "You've already reported this.",

    # ---- fotoğraflar ----
    "Yalnızca JPEG, PNG veya WebP yüklenebilir.":
        "Only JPEG, PNG or WebP images can be uploaded.",
    "Dosya 5 MB'den büyük olamaz.": "The file can't be larger than 5 MB.",
    "Dosya boş.": "The file is empty.",
    "Dosya içeriği görüntü formatıyla uyuşmuyor.":
        "The file's content doesn't match its image format.",
    "Fotoğraf şu an kaydedilemedi. Biraz sonra tekrar dene.":
        "The photo couldn't be saved right now. Try again shortly.",
    "Fotoğraf bulunamadı.": "Photo not found.",
    "Fotoğraf şu an yüklenemedi.": "The photo couldn't be loaded right now.",

    # ---- yönetici paneli ----
    "Silme gerekçesi boş olamaz.": "The deletion reason can't be empty.",
    "Rapor bulunamadı.": "Report not found.",
    "İçerik bulunamadı.": "Content not found.",
    "Bu içerik yönetici tarafından kaldırılmış; işaret temizlemek "
    "kaldırmayı geri almaz. Geri almak için 'restore' kullan.":
        "This content was removed by an admin; clearing the flag doesn't "
        "undo the removal. Use 'restore' to undo it.",
    "Bu içerik yönetici tarafından kaldırılmamış; zaten yayında.":
        "This content wasn't removed by an admin; it's already live.",
    "Bu ilan yönetici tarafından kaldırılmış. Yayına almak için "
    "POST /api/admin/listing/{id}/restore kullan.":
        "This listing was removed by an admin. Use "
        "POST /api/admin/listing/{id}/restore to publish it.",
    # Fiil, aşağıdaki iki cümle kalıbına yerleşir ("Kendini silemezsin.").
    "Kendini {verb}.": "You can't {verb} yourself.",
    "Başka bir yöneticiyi {verb}.": "You can't {verb} another admin.",
    "askıya alamazsın": "suspend",
    "silemezsin": "delete",
    "Kullanıcı bulunamadı.": "User not found.",
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def current_lang() -> str:
    """Şu anki isteğin dili ("tr" ya da "en")."""
    return _lang.get()


def localized(text: str, **values: object) -> str:
    """Türkçe kaynak metni isteğin diline çevirir ve yer tutucuları doldurur.

    Yalnızca `values`'ta adı geçen {ad} yer tutucuları doldurulur; geri
    kalanı olduğu gibi kalır (metindeki "/listing/{id}/restore" gibi).
    Değerler metne bir kez yerleştirilir ve yeniden taranmaz — yöneticinin
    askı notu gibi serbest metin "{...}" içerse de bozulmaz.
    """
    if _lang.get() == "en":
        english = EN.get(text, text)
        if isinstance(english, tuple):
            english = english[0] if values.get("n") == 1 else english[1]
        text = english
    if not values:
        return text
    return _PLACEHOLDER.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
        text,
    )


def negotiate(header: str | None) -> str:
    """`Accept-Language` başlığından desteklenen en uygun dili seçer.

    Ağırlığı (q) en yüksek desteklenen dil kazanır; eşitlikte önce yazılan.
    "en-US" gibi bölge ekli etiketler ana dile indirgenir. Desteklenen dil
    yoksa ya da başlık hiç yoksa Türkçe döner.
    """
    if not header:
        return DEFAULT_LANG
    best, best_q = DEFAULT_LANG, 0.0
    for part in header.split(","):
        tag, _, params = part.partition(";")
        lang = tag.strip().lower().split("-", 1)[0]
        if lang not in SUPPORTED_LANGS:
            continue
        q = 1.0
        for param in params.split(";"):
            key, _, value = param.partition("=")
            if key.strip().lower() == "q":
                try:
                    q = float(value)
                except ValueError:
                    q = 0.0
        if q > best_q:
            best, best_q = lang, q
    return best


class LanguageMiddleware:
    """İsteğin dilini `Accept-Language`'dan okuyup ContextVar'a yazar.

    Hata yanıtlarına `Vary: Accept-Language` eklenir: aynı adres dile göre
    farklı metin döndürdüğü için bir önbellek bir dildeki hatayı diğer dilde
    sunmamalı. Başarılı yanıtların gövdesi dile bağlı değil, onlara eklenmez.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header = None
        for name, value in scope.get("headers", []):
            if name == b"accept-language":
                header = value.decode("latin-1")
                break

        async def send_with_vary(message):
            if message["type"] == "http.response.start" and message["status"] >= 400:
                message.setdefault("headers", []).append(
                    (b"vary", b"Accept-Language")
                )
            await send(message)

        token = _lang.set(negotiate(header))
        try:
            await self.app(scope, receive, send_with_vary)
        finally:
            _lang.reset(token)
