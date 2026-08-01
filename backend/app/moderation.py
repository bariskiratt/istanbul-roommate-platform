"""İçerik denetimi — kural tabanlı katman.

Her zaman açıktır, dış bağımlılığı yoktur ve saf fonksiyonlardan oluşur;
böylece hızlı çalışır ve test edilebilir.

Burası bir KİRALIK EV İLANI sitesidir: masum bir ilanı engellemek, kaba bir
sözü kaçırmaktan çok daha kötüdür. Bu yüzden "block" YALNIZCA tartışmasız
ağır küfür, tartışmasız nefret söylemi ve tartışmasız cinsel taciz/tehdit
için üretilir. Sezgisel olan her şey (dolandırıcılık şüphesi, iletişim
bilgisi, site dışı yönlendirme, hafif hakaret, ayrımcılık şüphesi) EN FAZLA
"flag" üretir.

Tasarımın en büyük riski YANLIŞ POZİTİF: "sıkıntı", "sık sık", "ışık",
"amaç", "mal", "cunta", "fukara", "çıplak duvar" gibi masum kelimeler küfür
sanılırsa kullanıcı ilan açamaz hale gelir. Buna karşı dört önlem alındı:

1. Eşleşme kelime bazında yapılır (alt dize taraması yok) — "sikinti"
   içindeki "sik" tetiklenmez.
2. Türkçe karakter katlaması (ı→i, ş→s ...) yapılan metin ile katlanmamış
   metin ayrı tutulur. "sık" katlanınca "sik" olur; bu yüzden kısa ve
   çakışan kökler (sik, piç, göt) YALNIZCA katlanmamış metinde ve tam
   kelime olarak aranır.
3. `_SAFE_TOKENS` beyaz listesi: bilinen masum kelimeler hiçbir kurala
   girmeden atlanır.
4. Kısa İngilizce kökler (fuk, cunt) kullanılmaz; Türkçe kelimelerle
   çakıştıkları için ya tam kelime olarak aranır ya da hiç aranmaz.

Rakam-harf ikamesi (leetspeak) yalnızca harf sayısı rakam sayısından çok
olan kelimelerde uygulanır; böylece "51k TL" fiyatı "sik" gibi
okunmaz, ama "s1kt1r" yakalanır.

Kaçış (atlatma) girişimlerine karşı normalleştirme üç ek adım yapar:
sıfır genişlikli karakterler silinir, Kiril/Yunan homoglifleri Latin'e
eşlenir ve kelime araları yok sayılmış "sıkıştırılmış" bir kopya üzerinde
YALNIZCA yeterince uzun ve ayırt edici kökler aranır (bkz. `_JOINED_STEMS`).
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

# Tek kaynak ilkesi: "okunamayan içerik" işaretini crypto tanımlar, burada
# yeniden yazılmaz. (app.crypto yalnızca standart kütüphaneye bağlıdır;
# bu import modülün saflığını bozmaz ve döngü yaratmaz.)
from app.crypto import UNREADABLE

Kind = Literal["listing", "message"]
Action = Literal["allow", "flag", "block"]

# --------------------------------------------------------------------------
# Sebep kodları — API yanıtlarında ve yönetici incelemesinde kullanılır.
# --------------------------------------------------------------------------
KUFUR = "kufur"
HAKARET = "hakaret"
NEFRET = "nefret_soylemi"
CINSEL = "cinsel_icerik"
TACIZ = "taciz"
DOLANDIRICILIK = "dolandiricilik"
SITE_DISI = "site_disi_yonlendirme"
ILETISIM = "iletisim_bilgisi"

# Eşik değerler: bu puanı aşan içerik reddedilir / işaretlenir.
BLOCK_THRESHOLD = 1.0
FLAG_THRESHOLD = 0.4

# Olasılıksal kategorilerin (dolandırıcılık) verebileceği en yüksek ağırlık.
# BLOCK_THRESHOLD'un altındadır: bu kategori asla ilan/mesaj engellemez.
_SCAM_MAX = 0.9

# Çok uzun metinlerde regex maliyetini sınırla (ilan 2000, mesaj 2000 karakter).
MAX_SCAN_LENGTH = 8000


@dataclass
class ModerationResult:
    """Denetim sonucu.

    action: "allow" | "flag" | "block"
    reasons: sebep kodları ("kufur", "dolandiricilik:iban" gibi)
    score: 0.0 – 1.0 arası en yüksek ihlal ağırlığı
    """

    action: Action = "allow"
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0

    @property
    def blocked(self) -> bool:
        return self.action == "block"

    @property
    def flagged(self) -> bool:
        return self.action == "flag"


# --------------------------------------------------------------------------
# Normalize etme
# --------------------------------------------------------------------------

# Türkçe karakterleri ASCII karşılığına indirger. Yalnızca "sert" normalize
# etmede kullanılır; yumuşak normalize etme Türkçe harfleri korur.
_TR_FOLD = str.maketrans("çğıöşü", "cgiosu")

# Harf yerine rakam/sembol kullanımı (leetspeak).
_LEET = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
}

_NON_WORD = re.compile(r"[^0-9a-zçğıöşü]+")
_REPEAT = re.compile(r"(.)\1{2,}")

# Görünmez karakterler: "or​ospu" gibi kaçışları kırmak için silinir.
# (Boşluğa DEĞİL, hiçliğe çevrilir; yoksa kelimeyi bölerek atlatmaya yardım eder.)
_ZERO_WIDTH = dict.fromkeys(
    [
        0x00AD,  # soft hyphen
        0x200B,  # zero width space
        0x200C,  # zero width non-joiner
        0x200D,  # zero width joiner
        0x2060,  # word joiner
        0xFEFF,  # zero width no-break space
    ]
)

# Kiril / Yunan homoglifleri → Latin karşılığı. "оrospu" (Kiril о) gibi
# kaçışlar için. _NON_WORD bu harfleri boşluğa çevirip kelimeyi bölmeden
# ÖNCE uygulanır.
_HOMOGLYPHS = str.maketrans(
    {
        # Kiril
        "а": "a", "в": "b", "с": "c", "ԁ": "d", "е": "e", "ѕ": "s",
        "і": "i", "ј": "j", "к": "k", "м": "m", "н": "h", "о": "o",
        "р": "p", "т": "t", "у": "y", "х": "x", "ѵ": "v",
        # Yunan
        "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "μ": "m",
        "ν": "v", "ο": "o", "ρ": "p", "σ": "s", "τ": "t", "υ": "u",
        "χ": "x", "γ": "y",
    }
)


def _apply_leet(token: str) -> str:
    """Rakam-harf ikamesini yalnızca "kelime gibi duran" parçalarda uygular.

    "s1kt1r" → "siktir" (4 harf, 2 rakam) ama "51k" → "51k" (1 harf, 2 rakam),
    "8500" → "8500". Fiyat ve oda sayısı gibi sayıların küfüre dönüşmesini
    engeller.
    """
    letters = sum(1 for ch in token if ch.isalpha())
    others = sum(1 for ch in token if ch in _LEET)
    if letters < 2 or others >= letters:
        return token
    return "".join(_LEET.get(ch, ch) for ch in token)


def _lower_tr(text: str) -> str:
    """Türkçeye uygun küçültme (I → ı, İ → i)."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def _prepare(text: str, *, fold: bool) -> str:
    text = text[:MAX_SCAN_LENGTH].translate(_ZERO_WIDTH)
    text = unicodedata.normalize("NFKC", text)
    text = _lower_tr(text)
    text = text.translate(_HOMOGLYPHS)
    text = " ".join(_apply_leet(tok) for tok in text.split())
    if fold:
        text = text.translate(_TR_FOLD)
    text = _NON_WORD.sub(" ", text)
    text = _REPEAT.sub(r"\1", text)  # "siiiktir" → "siktir"
    return " ".join(text.split())


def normalize(text: str) -> str:
    """Sert normalize etme: küçük harf + leetspeak + Türkçe karakter katlama.

    Sözlük eşleşmelerinin çoğu bu biçim üzerinde yapılır.
    """
    return _prepare(text, fold=True)


def normalize_soft(text: str) -> str:
    """Yumuşak normalize etme: Türkçe harfler korunur ("sık" ≠ "sik")."""
    return _prepare(text, fold=False)


def _tokens(normalized: str) -> list[str]:
    return normalized.split()


def _merge_short_runs(tokens: list[str]) -> list[str]:
    """Harflere ayırarak yapılan kaçışı yakalar: "s i k t i r" → "siktir".

    Yalnızca art arda gelen 1-2 harflik parçalar birleştirilir; normal
    cümleler bu şekilde birleşmediği için yanlış pozitif riski düşüktür.
    """
    merged: list[str] = []
    run: list[str] = []
    for tok in tokens:
        if len(tok) <= 2:
            run.append(tok)
            continue
        if len(run) >= 3:
            merged.append("".join(run))
        run = []
    if len(run) >= 3:
        merged.append("".join(run))
    return merged


# --------------------------------------------------------------------------
# Sözlükler
# --------------------------------------------------------------------------

# Masum ama sözlüklere yakın duran kelimeler — hiçbir kurala sokulmaz.
_SAFE_TOKENS = frozenset(
    {
        "sikinti", "sikintili", "sikintisiz", "sikintida", "siki", "sikica",
        "sikisik", "sikismis", "sikistir", "sikma", "sikmak", "sikilmis",
        "sik",  # sert biçimde "sık" ile çakışır; sıkı denetim soft metinde
        "amac", "amacli", "amaclar", "ama", "aman", "amir", "amele", "amel",
        "ambalaj", "ambar", "aminoasit", "amerika", "amerikan",
        "got", "gotik",  # "göt" soft metinde ayrıca aranır
        "pic", "pics", "picture", "pictures",
        "mal", "malzeme", "maliyet", "malikane", "mali",
        "alcak", "alcakta", "hayvan", "domuz", "esek", "hiyar",
        "isik", "isikli", "isiktir", "kisik", "acik", "sicak", "sicakligi",
        "yara", "yarali", "yarim", "yaris", "yarin",
        "class", "pass", "assist", "assistant", "assume", "bass", "grass",
        "analiz", "analitik",
    }
)

# Türkçe karakter katlamasının ürettiği sahte eşleşmeler: "şıktır" → "siktir",
# "ışıktır" → "isiktir". Bu ön eklerle BAŞLAYAN kelimeler (katlanmamış hâlde)
# hiçbir küfür kuralına sokulmaz — küfür bu kelimelerin hiçbirinde ı/ş ile
# yazılmaz. ("Daire oldukça şıktır." engellenmemeli.)
_FOLD_ARTIFACT_PREFIXES = ("şık", "ışık", "kısık", "aşık", "şıp")

# Ağır küfür / hakaret (engellenir). Kelime BAŞLANGICI eşleşmesi yapılır;
# Türkçe ekler ("orospunun", "siktirir") bu sayede yakalanır.
_TR_STRONG_STEMS = (
    "orospu", "oruspu", "orospucocu", "amcik", "amina", "aminakoy",
    "amk", "amq", "yarrak", "yarak", "dalyarak", "dallama",
    "gotver", "gotveren", "gotlek", "gotoglan", "pezevenk",
    "kahpe", "kaltak", "kancik", "sikeyim", "sikerim", "sikiyim",
    "siktir", "siktim", "siktig", "sikik", "sikimde", "sikimin",
    "hasiktir", "gavat", "ibne", "pust", "serefsiz", "namussuz",
    "haysiyetsiz", "yavsak", "kerhane", "fahise", "surtuk", "kevase",
    "godos", "zibidi", "sikko", "anani", "ananin", "ananiz",
    "avradini", "bacini", "sulaleni", "ecdadini", "kodugum",
    "pickurusu", "sikimsonik", "amcikagizli",
)
# NOT: "kodumun" bilerek listede yok — "kodumun içinde hata var" yazan bir
# yazılımcının ilanını engellemek, kaçırılan küfürden çok daha pahalı.

# Kısa ve çakışmalı kökler: yalnızca Türkçe harfler korunmuş metinde ve
# TAM KELİME olarak aranır. "sık", "ışık", "picture" tetiklemez.
_TR_STRONG_SOFT_EXACT = frozenset({"sik", "sike", "sikim", "piç", "göt", "götü"})

# Hafif hakaret (işaretlenir, engellenmez).
# NOT: "manyak" listede yok — Türkçede "manyak güzel bir daire" gibi
# pekiştireç kullanımı hakaret kullanımından çok daha yaygın.
_TR_MILD_STEMS = (
    "salak", "aptal", "ahmak", "gerizekali", "gerzek", "dangalak",
    "embesil", "denyo", "budala", "avanak", "andaval", "ukala",
    "ezik", "sersem", "gudubet", "sapik", "aptallik",
)

# İngilizce ağır küfür (kelime başlangıcı eşleşmesi).
# Kısa kökler kullanılmaz: "fuk" → "fukara", "cunt" → "cunta" masum
# Türkçe kelimelerini yakalıyordu. Tam kelime gerekenler
# `_EN_STRONG_EXACT` içindedir.
_EN_STRONG_STEMS = (
    "fuck", "motherfuck", "shit", "bullshit", "bitch", "bastard",
    "asshole", "arsehole", "dickhead", "nigg", "faggot",
    "whore", "slut", "wanker", "retard", "dumbass", "jackass",
    "douche", "scumbag", "shithead", "dipshit", "bollock", "twat",
    "prick", "skank", "pissoff", "cocksuck", "wtfff",
)

# İngilizce: alt dize riski taşıyanlar tam kelime olarak aranır.
_EN_STRONG_EXACT = frozenset(
    {
        "ass", "arse", "dick", "cock", "pussy", "fag", "tits", "stfu",
        "gtfo", "cunt", "cunts",
    }
)

_EN_MILD_STEMS = ("stupid", "idiot", "moron", "loser", "sucks", "jerkoff")
_EN_MILD_EXACT = frozenset({"damn", "crap", "piss", "jerk", "dumb", "wtf"})

# Nefret söylemi: hakaret niteliğindeki etnik/dinsel/cinsel yönelim ifadeleri.
_HATE_STEMS = (
    "zenci", "cingene", "nigg", "faggot", "ibneler", "gavur",
)

# Barınmada ayrımcılık kalıpları — "sadece kız/erkek" gibi normal tercihler
# kapsam dışıdır; yalnızca etnik köken / din / cinsel yönelim hedeflenir.
# Bunlar sezgiseldir, bu yüzden ASLA "block" üretmez (bkz. _HATE_PATTERN_WEIGHT).
_HATE_PATTERNS = (
    re.compile(
        r"\b(kurt|suriyeli|arap|afgan|iranli|ermeni|yahudi|alevi|sunni|roman|"
        r"cingene|zenci|siyahi|escinsel|gay|lezbiyen|trans)\w*\s+"
        r"(istemiyor\w*|istemem|olmasin|kabul\s+etmiyor\w*|giremez|alinmaz|"
        r"kalamaz|olmayacak|yasak)"
    ),
    # "sadece turk/beyaz ..." tek başına çok geniştir: "sadece Türkçe
    # konuşuyorum", "sadece beyaz eşya var" masum cümlelerdir. Bu yüzden
    # yalnızca KİŞİYE yönelik açık dışlama biçimi aranır.
    re.compile(
        r"\bsadece\s+(turk|turkler|musluman\w*|sunni\w*|beyaz|beyazlar)\s+"
        r"(kiraci\w*|ogrenci\w*|vatandas\w*|kisi\w*|erkek\w*|kadin\w*|"
        r"birey\w*|insan\w*|aile\w*|arkadas\w*|ev\s*arkadas\w*)"
    ),
)
# Ayrımcılık kalıpları olasılıksaldır: en fazla işaretlenir.
_HATE_PATTERN_WEIGHT = 0.6

# Cinsel içerik — yalnızca tartışmasız ifadeler. "çıplak"/"soyunmuş" tek
# başına masumdur ("çıplak duvarlar boyanacak"), bu yüzden sözlükte değil
# yalnızca "gönder/at/yolla" fiilleriyle birlikte kalıpta aranır. "seksi"
# de çıkarıldı: "seksiyon" gibi kelimelerle çakışıyordu.
_SEXUAL_STEMS = (
    "porno", "mastur", "orgazm", "penis", "vajina", "escort", "eskort",
    "jigolo", "sexchat", "nudes",
)
_SEXUAL_EXACT = frozenset({"seks", "sex", "nude", "porn"})
_SEXUAL_PATTERNS = (
    # "kira karşılığında ilişki", "ücretsiz kalabilirsin karşılığında birlikte"
    re.compile(
        r"karsilig\w*\s+(?:\w+\s+){0,4}?"
        r"(iliski|birliktelik|seks|yatak|sevgili|masaj|arkadaslik)"
    ),
    re.compile(
        r"(iliski|birliktelik|seks|yatak|sevgili)\w*\s+(?:\w+\s+){0,4}?karsilig\w*"
    ),
    re.compile(r"(ciplak|soyun\w*|ic\s*camasir\w*)\s+(?:\w+\s+){0,3}?"
               r"(gonder|at|yolla|paylas)\w*"),
)

# Taciz / tehdit.
_HARASSMENT_PATTERNS = (
    re.compile(r"\bseni\s+(bulurum|bulacagim|gebertirim|oldururum|dograrim)\b"),
    # "doğrarım" tek başına listede yok: "sebzeleri doğrarım" masumdur;
    # yalnızca "seni doğrarım" biçiminde (üstteki kalıp) tehdit sayılır.
    re.compile(r"\b(oldururum|oldurecegim|gebertirim|gebertecegim)\b"),
    re.compile(r"\bkafani\s+(kirarim|patlatirim|kopartirim)\b"),
    re.compile(r"\b(adresini|nerede\s+oturdugunu)\s+biliyorum\b"),
    re.compile(r"\bcanina\s+okurum\b"),
    re.compile(r"\b(doverim|dovecegim|pisman\s+ederim|pisman\s+edecegim)\b"),
    re.compile(r"\b(i\s+will\s+kill\s+you|kill\s+yourself|kys)\b"),
    re.compile(r"\bwatch\s+your\s+back\b"),
)

# --------------------------------------------------------------------------
# Kelimeyi parçalayarak yapılan kaçış ("oros pu çocuğu", "geber tirim")
# --------------------------------------------------------------------------
#
# Bunun için kelime araları yok sayılmış ("sıkıştırılmış") bir kopya üretilir
# ve kökler o kopyada da aranır. Bu kopya yanlış pozitife çok açıktır
# ("çok amaçlı" → "cokamacli"), bu yüzden iki sıkı kısıt uygulanır:
#
#   1. Yalnızca >= 6 harflik, tek anlamı olan kökler aranır.
#   2. Eşleşme bir KELİME BAŞINDA başlamak zorundadır. Böylece "ışıktır" /
#      "kısıktır" içindeki "siktir" (kelimenin ortasında başlıyor) tetiklemez,
#      ama "s(ik) tir" gibi parçalanmış yazımlar yakalanır.
#
# Ayrıca beyaz listedeki kelimelerle başlayan eşleşmeler atlanır: "şık tıraş"
# → "siktiras" gibi tesadüfleri önler.
_JOINED_STEMS: tuple[tuple[str, str], ...] = (
    ("orospu", KUFUR),
    ("oruspu", KUFUR),
    ("aminakoy", KUFUR),
    ("amcigi", KUFUR),
    ("yarrak", KUFUR),
    ("dalyarak", KUFUR),
    ("pezevenk", KUFUR),
    ("siktir", KUFUR),
    ("siktim", KUFUR),
    ("sikeyim", KUFUR),
    ("sikerim", KUFUR),
    ("sikiyim", KUFUR),
    ("gotveren", KUFUR),
    ("namussuz", KUFUR),
    ("haysiyetsiz", KUFUR),
    ("motherfuck", KUFUR),
    ("gebertirim", TACIZ),
    ("gebertecegim", TACIZ),
    ("oldururum", TACIZ),
    ("oldurecegim", TACIZ),
)
# NOT: "şerefsiz" bilerek yok — "şeref sizin olsun" ile çakışıyor.

# --------------------------------------------------------------------------
# Dolandırıcılık ve iletişim bilgisi kalıpları
# --------------------------------------------------------------------------

_URGENCY = (
    "acil", "acilen", "hemen", "son gun", "bugun son", "kacirma",
    "kacirmayin", "simdi ode", "yarina kadar", "sinirli sure",
    "firsat kacmasin", "cok hizli", "ilk gelen",
)
# Para talebi: kendi başına da anlamlı olan, doğrudan "bana para gönder"
# anlamı taşıyan ifadeler.
_MONEY_MOVE = (
    "para gonder", "para yolla", "para at", "western union",
    "kripto", "bitcoin", "usdt", "hesabima yatir", "hesap numaram",
    "kart bilgileri", "kart numaran", "iban numaram",
)
# Ödeme kanalları: Türkiye'de kira dilinin OLAĞAN parçası ("depozito havale
# ile alınır", "Papara ile ödeyebilirim"). Tek başına hiçbir şey üretmez;
# yalnızca "evi görmeden" gibi güçlü bir sinyalle birleşince anlam kazanır.
_PAYMENT_CHANNEL = (
    "havale", "eft", "papara", "ininal", "payfix",
)
_DEPOSIT = (
    "kapora", "kaparo", "depozito", "on odeme", "pesinat",
    "rezervasyon ucreti", "yer ayirma ucreti",
)
_SIGHT_UNSEEN = (
    "gormeden", "gormeye gerek yok", "goremezsiniz", "yurt disindayim",
    "ulke disindayim", "sehir disindayim", "anahtari kargo",
    "kargoyla gonderirim", "anahtari kargoyla",
)
_OFFSITE = (
    "whatsapp", "whatsup", "watsapp", "telegram", "instagram",
    "dm at", "dm den", "buradan konusmayalim", "site disinda",
    "numaramdan yaz", "wp den yaz",
)

# TR IBAN: "TR33 0006 1005 1978 6457 8413 26" (boşluklu da olabilir).
_IBAN_RE = re.compile(r"\btr\s?\d{2}(?:\s?\d){20,22}\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
# Türk cep telefonu: 05xx xxx xx xx / +90 5xx ... / 5xxxxxxxxx
_PHONE_RE = re.compile(
    r"(?:\+?9\s*0[\s.\-/]*)?0?[\s.\-/]*5\d{2}[\s.\-/]*\d{3}[\s.\-/]*\d{2}"
    r"[\s.\-/]*\d{2}\b"
)
_LONG_DIGITS_RE = re.compile(r"\d{10,}")


def _compile_group(words: tuple[str, ...]) -> tuple[tuple[str, re.Pattern], ...]:
    """Anahtar kelime grubunu kelime sınırlı desenlere çevirir.

    Kısa kelimeler tam eşleşir ("acil", "açılır"ın içinde tetiklenmesin);
    6 harf ve üzeri ifadelerde Türkçe ekler serbesttir ("kaporayı").
    """
    compiled: list[tuple[str, re.Pattern]] = []
    for word in words:
        escaped = r"\s+".join(re.escape(part) for part in word.split())
        tail = r"\w*" if len(word) >= 6 else r"\b"
        compiled.append((word, re.compile(r"\b" + escaped + tail)))
    return tuple(compiled)


_URGENCY_RE = _compile_group(_URGENCY)
_MONEY_MOVE_RE = _compile_group(_MONEY_MOVE)
_PAYMENT_CHANNEL_RE = _compile_group(_PAYMENT_CHANNEL)
_DEPOSIT_RE = _compile_group(_DEPOSIT)
_SIGHT_UNSEEN_RE = _compile_group(_SIGHT_UNSEEN)
_OFFSITE_RE = _compile_group(_OFFSITE)


# --------------------------------------------------------------------------
# Bulgular
# --------------------------------------------------------------------------


class _Findings:
    """İhlalleri toplar; en yüksek ağırlık sonucun puanı olur."""

    def __init__(self) -> None:
        self._reasons: list[str] = []
        self._score = 0.0

    def add(self, code: str, weight: float) -> None:
        if code not in self._reasons:
            self._reasons.append(code)
        self._score = max(self._score, weight)

    def result(self) -> ModerationResult:
        if self._score >= BLOCK_THRESHOLD:
            action: Action = "block"
        elif self._score >= FLAG_THRESHOLD:
            action = "flag"
        else:
            action = "allow"
        return ModerationResult(
            action=action, reasons=list(self._reasons), score=round(self._score, 2)
        )


def _match_stems(
    tokens: list[str],
    stems: tuple[str, ...],
    *,
    safe: frozenset[str] = _SAFE_TOKENS,
) -> str | None:
    for token in tokens:
        if token in safe:
            continue
        for stem in stems:
            if token.startswith(stem):
                return stem
    return None


def _match_exact(
    tokens: list[str],
    words: frozenset[str],
    *,
    safe: frozenset[str] = _SAFE_TOKENS,
) -> str | None:
    for token in tokens:
        if token in safe:
            continue
        if token in words:
            return token
    return None


def _match_joined(tokens: list[str]) -> tuple[str, str] | None:
    """Kelime aralarını yok sayarak uzun kökleri arar.

    Eşleşme yalnızca bir kelimenin başladığı yerden başlayabilir; böylece
    "ışıktır"/"kısıktır" içindeki "siktir" tetiklenmez ama "oros pu" ve
    "geber tirim" yakalanır.
    """
    joined = "".join(tokens)
    offset = 0
    for token in tokens:
        start = offset
        offset += len(token)
        if token in _SAFE_TOKENS:
            continue
        for stem, code in _JOINED_STEMS:
            if joined.startswith(stem, start):
                return stem, code
    return None


def _search_group(
    text: str, group: tuple[tuple[str, re.Pattern], ...]
) -> str | None:
    for word, pattern in group:
        if pattern.search(text):
            return word
    return None


# --------------------------------------------------------------------------
# Kurallar
# --------------------------------------------------------------------------


def _check_language(hard: str, soft: str, found: _Findings) -> None:
    """Küfür, hakaret, nefret söylemi ve cinsel içerik."""
    soft_tokens = _tokens(soft)
    # Katlama artığı kelimeleri ("şıktır" → "siktir") tümüyle dışarıda bırak.
    # hard ve soft aynı boru hattından geçtiği için kelimeler birebir hizalıdır.
    word_tokens = [
        token
        for token, raw in zip(_tokens(hard), soft_tokens)
        if not raw.startswith(_FOLD_ARTIFACT_PREFIXES)
    ]
    hard_tokens = word_tokens + _merge_short_runs(word_tokens)

    joined = _match_joined(word_tokens)

    hit = _match_stems(hard_tokens, _TR_STRONG_STEMS) or _match_stems(
        hard_tokens, _EN_STRONG_STEMS
    )
    if hit is None:
        hit = _match_exact(hard_tokens, _EN_STRONG_EXACT)
    if hit is None:
        # Kısa/çakışmalı kökler: Türkçe harfler korunmuş metinde tam kelime.
        # Beyaz liste burada uygulanmaz — "sık" zaten "sik"ten farklı yazılır.
        hit = _match_exact(soft_tokens, _TR_STRONG_SOFT_EXACT, safe=frozenset())
    if hit is None and joined is not None and joined[1] == KUFUR:
        hit = joined[0]
    if hit is not None:
        found.add(f"{KUFUR}:{hit}", 1.0)

    mild = (
        _match_stems(hard_tokens, _TR_MILD_STEMS)
        or _match_stems(hard_tokens, _EN_MILD_STEMS)
        or _match_exact(hard_tokens, _EN_MILD_EXACT)
    )
    if mild is not None:
        found.add(f"{HAKARET}:{mild}", 0.5)

    # Tartışmasız nefret ifadeleri engellenir; ayrımcılık kalıpları
    # olasılıksaldır, en fazla işaretlenir.
    hate = _match_stems(hard_tokens, _HATE_STEMS)
    if hate is not None:
        found.add(f"{NEFRET}:{hate}", 1.0)
    else:
        for pattern in _HATE_PATTERNS:
            if pattern.search(hard):
                found.add(f"{NEFRET}:ayrimcilik", _HATE_PATTERN_WEIGHT)
                break

    sexual = _match_stems(hard_tokens, _SEXUAL_STEMS) or _match_exact(
        hard_tokens, _SEXUAL_EXACT
    )
    if sexual is None:
        for pattern in _SEXUAL_PATTERNS:
            if pattern.search(hard):
                sexual = "teklif"
                break
    if sexual is not None:
        found.add(f"{CINSEL}:{sexual}", 1.0)

    threat = joined is not None and joined[1] == TACIZ
    if not threat:
        threat = any(pattern.search(hard) for pattern in _HARASSMENT_PATTERNS)
    if threat:
        found.add(f"{TACIZ}:tehdit", 1.0)


def _check_scam(hard: str, raw: str, kind: Kind, found: _Findings) -> None:
    """Dolandırıcılık kalıpları — hem ilanlarda hem sohbette geçerli.

    Dolandırıcılık tespiti doğası gereği olasılıksaldır: "depozito havale ile
    alınır", "acil kiracı aranıyor" cümleleri Türkiye'de tamamen olağandır.
    Bu yüzden bu kategori HİÇBİR ZAMAN "block" üretmez (en yüksek ağırlık
    `_SCAM_MAX` < BLOCK_THRESHOLD); yalnızca yönetici incelemesi için
    işaretler. Ayrıca hiçbir sinyal TEK BAŞINA bulgu üretmez; en az iki
    bağımsız işaretin bir araya gelmesi gerekir.
    """
    has_iban = bool(_IBAN_RE.search(raw))
    urgency = _search_group(hard, _URGENCY_RE)
    money = _search_group(hard, _MONEY_MOVE_RE)
    channel = _search_group(hard, _PAYMENT_CHANNEL_RE)
    deposit = _search_group(hard, _DEPOSIT_RE)
    unseen = _search_group(hard, _SIGHT_UNSEEN_RE)
    offsite = _search_group(hard, _OFFSITE_RE)

    if has_iban and (urgency or money or deposit):
        found.add(f"{DOLANDIRICILIK}:iban_aciliyet", _SCAM_MAX)
    if unseen and (deposit or money or channel):
        # "Evi görmeden kapora gönder, anahtarı kargoyla yollarım."
        found.add(f"{DOLANDIRICILIK}:gormeden_kapora", _SCAM_MAX)
    if money and urgency:
        found.add(f"{DOLANDIRICILIK}:para_transferi", 0.6)

    if offsite and (money or deposit or urgency):
        found.add(f"{DOLANDIRICILIK}:site_disi_odeme", 0.6)
    elif offsite and kind == "listing":
        # Sohbette WhatsApp paylaşmak normaldir; ilanda site dışına çekme
        # denemesi sayılır.
        found.add(f"{SITE_DISI}:{offsite}", 0.5)


def _check_contact(raw: str, found: _Findings) -> None:
    """İletişim bilgisi paylaşımı — YALNIZCA ilanlarda çağrılır."""
    if _PHONE_RE.search(raw) or _LONG_DIGITS_RE.search(raw):
        found.add(f"{ILETISIM}:telefon", 0.4)
    if _EMAIL_RE.search(raw):
        found.add(f"{ILETISIM}:eposta", 0.4)
    if _IBAN_RE.search(raw):
        found.add(f"{ILETISIM}:iban", 0.4)


def check_rules(text: str, *, kind: Kind) -> ModerationResult:
    """Yalnızca kural tabanlı denetim (yapay zeka katmanı çalıştırılmaz)."""
    if not text or not text.strip():
        return ModerationResult()

    hard = normalize(text)
    soft = normalize_soft(text)
    found = _Findings()

    _check_language(hard, soft, found)
    _check_scam(hard, text, kind, found)
    if kind == "listing":
        _check_contact(text, found)

    return found.result()


def check(text: str, *, kind: Kind) -> ModerationResult:
    """Ortak giriş noktası: kural katmanı + (varsa) yapay zeka katmanı.

    Kural katmanı zaten "block" dediyse yapay zekaya gidilmez (gereksiz
    maliyet ve gecikme). Yapay zeka katmanı yoksa ya da hata verirse
    sessizce kural sonucuna düşülür.
    """
    result = check_rules(text, kind=kind)
    if result.blocked or not text or not text.strip():
        return result
    ai_result = _run_ai(text, kind=kind)
    if ai_result is None:
        return result
    return merge(result, ai_result)


def _run_ai(text: str, *, kind: Kind) -> ModerationResult | None:
    """Yapay zeka katmanını çağırır; kapalıysa veya hata olursa None döner."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        from app import moderation_ai  # geç import: modül saf kalsın

        return moderation_ai.classify(text, kind=kind)
    except Exception:  # noqa: BLE001 — denetim kullanıcı akışını bloke etmemeli
        return None


_ACTION_ORDER: dict[str, int] = {"allow": 0, "flag": 1, "block": 2}


def merge(first: ModerationResult, second: ModerationResult) -> ModerationResult:
    """İki sonucu birleştirir: daha katı olan kazanır, sebepler toplanır.

    Kural + yapay zeka katmanlarını birleştirmek için kullanılır; ilan
    başlığı ve açıklaması ayrı ayrı denetlendiği için (bkz. app/listings.py)
    kaydın tek bir işaret durumuna indirgenmesinde de kullanılır.
    """
    reasons = list(first.reasons)
    for reason in second.reasons:
        if reason not in reasons:
            reasons.append(reason)
    action = (
        first.action
        if _ACTION_ORDER[first.action] >= _ACTION_ORDER[second.action]
        else second.action
    )
    return ModerationResult(
        action=action, reasons=reasons, score=max(first.score, second.score)
    )


# --------------------------------------------------------------------------
# Kullanıcıya gösterilecek metin
# --------------------------------------------------------------------------

_MESSAGES: dict[str, str] = {
    KUFUR: "küfür veya ağır hakaret",
    HAKARET: "hakaret içeren ifade",
    NEFRET: "nefret söylemi veya ayrımcılık",
    CINSEL: "cinsel içerik",
    TACIZ: "taciz veya tehdit",
    DOLANDIRICILIK: "dolandırıcılık şüphesi taşıyan ifade",
    SITE_DISI: "site dışına yönlendirme",
    ILETISIM: "iletişim bilgisi paylaşımı",
}


# Yönetici bir mesajı "kaldır" ile incelediğinde satır SİLİNMEZ (sohbet akışı
# bozulmasın); yalnızca içerik bu sabitle değiştirilir.
#
# DİLDEN BAĞIMSIZ bir işarettir, kullanıcıya gösterilecek metin DEĞİLDİR:
# arayüz bu sabiti tanıyıp kendi dilinde bir karşılık basar (bkz. i18n ve
# crypto.UNREADABLE'da aynı desen). Değeri değiştirmek arayüzün çevirisini bozar.
# Şifrelenmeden düz yazılır — crypto.decrypt "enc:v1:" ile başlamayan değeri
# olduğu gibi döndürdüğü için sabit istemciye bozulmadan ulaşır.
REMOVED_CONTENT = "[removed_by_moderation]"

# Sunucunun ürettiği, arayüzün SİSTEM METNİ olarak bastığı dilden bağımsız
# işaretlerin TAMAMI. Tek kaynak burasıdır: crypto.UNREADABLE buraya
# import edilir, admin.py REMOVED_CONTENT'i buradan okur.
#
# Neden gerekli: kullanıcı içeriğine bu dizelerden birini yazmak, arayüzü
# kandırıp "Bu mesaj moderasyon tarafından kaldırıldı." / "Bu mesaj
# okunamıyor." cümlesini bastırıyordu — yani kullanıcı sistemin ağzından
# konuşabiliyordu. Ayrıca yönetici panelinde "Mesajı kaldır" düğmesi metin
# sabite eşitse gizlendiği için sahte sabiti yazan kullanıcının mesajı
# rapor kuyruğundan kaldırılamıyordu. Yazma anında reddediliyor.
SYSTEM_MARKERS: tuple[str, ...] = (REMOVED_CONTENT, UNREADABLE)

_SYSTEM_MARKERS_FOLDED = frozenset(marker.casefold() for marker in SYSTEM_MARKERS)

# Kullanıcıya gösterilen ret metni. Sabitin kendisini İÇERMEZ: hata mesajına
# yazsaydık kullanıcıya doğru yazımı öğretmiş olurduk.
SYSTEM_MARKER_REJECTION = (
    "Bu metin sistemin kendi kullandığı bir işaretle aynı; "
    "başka bir şey yazman gerekiyor."
)

# Alan bazlı ret gövdesinde bu redde verilen sebep kodu (bkz. app/listings.py).
# Denetim sözlüğünden gelmez: içerik "kötü" değil, sistem metnini taklit ediyor.
SYSTEM_MARKER = "sistem_isareti"


def is_system_marker(text: str | None) -> bool:
    """Kullanıcı girdisi sistem sabitlerinden birini taklit ediyor mu.

    Yalnızca metnin TAMAMI sabite eşitse True döner. Cümle içinde geçmesi
    ("mesajım [unreadable] görünüyor") masumdur ve arayüzü kandırmaz —
    arayüz tam eşitlik arar.
    """
    if not text:
        return False
    return text.strip().casefold() in _SYSTEM_MARKERS_FOLDED


def reasons_csv(result: ModerationResult) -> str | None:
    """İşaretleme gerekçelerini tek sütuna yazılacak biçime getirir.

    Sebep kodları ("kufur", "dolandiricilik:iban_aciliyet") virgülle birleşir.
    İçerik işaretlenmediyse None döner — temiz kayıtta gerekçe saklanmaz.
    """
    if not result.flagged or not result.reasons:
        return None
    return ",".join(result.reasons)


def split_reasons(raw: str | None) -> list[str]:
    """flag_reasons sütunundaki virgüllü dizeyi listeye çevirir."""
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def reason_codes(reasons: list[str]) -> list[str]:
    """Sebep kodlarını ayrıntısız ana kategorilere indirger.

    "kufur:siktir" -> "kufur". Ayrıntı kısmı yönetici kuyruğu için saklanır
    ama KULLANICIYA DÖNMEZ: eşleşen kök kullanıcının yazdığı kelimenin ta
    kendisi olabilir ve hata gövdesine yansıması hem gereksiz hem de
    "hangi kelimeyi değiştirirsem geçerim" denemesini kolaylaştırır.
    """
    codes: list[str] = []
    for reason in reasons:
        code = reason.split(":", 1)[0]
        if code not in codes:
            codes.append(code)
    return codes


def describe(reasons: list[str], subject: str = "İçerikte") -> str:
    """Sebep kodlarını kullanıcıya gösterilecek Türkçe cümleye çevirir.

    `subject` cümlenin öznesini değiştirir ("Başlıkta", "Açıklamada"); ilan
    uçları hangi ALANIN reddedildiğini böyle söyler. Metin her zaman sabit
    sözlükten üretilir — kullanıcının yazdığı hiçbir şey buraya sızmaz.
    """
    labels: list[str] = []
    for reason in reasons:
        label = _MESSAGES.get(reason.split(":", 1)[0])
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return f"{subject} topluluk kurallarımıza uymayan bir ifade tespit edildi."
    return f"{subject} " + ", ".join(labels) + " tespit edildi."
