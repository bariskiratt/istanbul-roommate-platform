"""Sunucu metinlerinin dili: Accept-Language ile Türkçe / İngilizce.

Arayüz İngilizce moddayken hata mesajları da İngilizce gelmeli; başlık
yoksa (API'yi doğrudan çağıranlar, diğer testler) eskisi gibi Türkçe.
"""

import ast
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app import auth, i18n, listings, moderation
from app.db import Base, get_db
from app.i18n import EN, localized, negotiate
from app.main import app

APP_DIR = Path(__file__).resolve().parent.parent / "app"
EN_HEADERS = {"Accept-Language": "en"}

EV_ILANI = {
    "type": "ev_ilani",
    "title": "Kadıköy'de güneşli 2+1",
    "description": "Moda'ya 5 dakika, geniş salon.",
    "district": "Kadıköy",
    "photos": [f"https://example.com/{i}.jpg" for i in range(3)],
    "rent": 18000,
    "room_count": "2+1",
}


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def english():
    """İstek dışında (birim testlerde) dili İngilizceye çevirir."""
    token = i18n._lang.set("en")
    yield
    i18n._lang.reset(token)


def _auth_headers(client, email="ali@uni.edu.tr") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---- dil seçimi ----


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, "tr"),
        ("", "tr"),
        ("en", "en"),
        ("tr", "tr"),
        ("en-US,en;q=0.9", "en"),
        ("tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7", "tr"),
        ("tr;q=0.5, en;q=0.8", "en"),
        # Desteklenmeyen dil Türkçeye düşer; desteklenen bir dil varsa o seçilir.
        ("de-DE,de;q=0.9", "tr"),
        ("de-DE,de;q=0.9,en;q=0.5", "en"),
        # q=0 "istemiyorum" demektir.
        ("en;q=0", "tr"),
        ("en;q=abc", "tr"),
    ],
)
def test_negotiate(header, expected):
    assert negotiate(header) == expected


# ---- localized ----


def test_localized_varsayilan_turkce():
    assert localized("İlan bulunamadı.") == "İlan bulunamadı."


def test_localized_ingilizce(english):
    assert localized("İlan bulunamadı.") == "Listing not found."


def test_localized_sozlukte_olmayan_metin_turkce_kalir(english):
    assert localized("Sözlükte olmayan bir cümle.") == "Sözlükte olmayan bir cümle."


def test_localized_yer_tutucular(english):
    assert (
        localized("Yaş {min}-{max} aralığında olmalı.", min=17, max=99)
        == "Age must be between 17 and 99."
    )


def test_localized_tekil_cogul(english):
    assert localized("{n} saat", n=1) == "1 hour"
    assert localized("{n} saat", n=2) == "2 hours"
    assert localized("{n} dakika", n=15) == "15 minutes"


def test_localized_degerleri_yeniden_taramaz():
    # Yöneticinin serbest notu "{...}" içerse de metne aynen girer.
    text = localized("{detail} Sebep: {reason}", detail="Askı.", reason="{detail}")
    assert text == "Askı. Sebep: {detail}"


def test_localized_adi_gecmeyen_yer_tutucuya_dokunmaz(english):
    text = localized(
        "Bu ilan yönetici tarafından kaldırılmış. Yayına almak için "
        "POST /api/admin/listing/{id}/restore kullan."
    )
    assert "/listing/{id}/restore" in text


# ---- sözlüğün bütünlüğü ----


def _placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


@pytest.mark.parametrize("source", sorted(EN))
def test_ceviri_yer_tutuculari_kaynakla_ayni(source):
    english = EN[source]
    variants = english if isinstance(english, tuple) else (english,)
    for variant in variants:
        assert variant.strip(), source
        assert _placeholders(variant) == _placeholders(source), source


def _app_modules():
    for path in sorted(APP_DIR.glob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"))


def _is_raw_text(node: ast.AST) -> bool:
    """Düz metin ya da f-string mi (yani localized ile sarılmamış)."""
    return isinstance(node, ast.JoinedStr) or (
        isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


def _literal_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_her_localized_cagrisinin_ingilizcesi_var():
    """`localized("...")` ile sarılan her metin sözlükte bulunmalı.

    Sözlükte olmayan metin çalışma anında Türkçe kalır; hata vermez, bu
    yüzden eksik çeviriyi ancak bu test yakalar.
    """
    missing = []
    for path, tree in _app_modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) == "localized":
                text = _literal_text(node.args[0]) if node.args else None
                if text is not None and text not in EN:
                    missing.append(f"{path.name}:{node.lineno}: {text}")
    assert not missing, "İngilizcesi eksik metinler:\n" + "\n".join(missing)


def test_kullaniciya_donen_metinler_localized_ile_sarili():
    """HTTPException ve doğrulayıcı ValueError'ları düz metin taşımamalı.

    Düz metin yazılırsa İngilizce modda Türkçe görünür. Metni
    `localized(...)` ile sarıp İngilizcesini app/i18n.py'deki EN'e ekle.
    """
    raw = []
    for path, tree in _app_modules():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name == "HTTPException":
                for kw in node.keywords:
                    if kw.arg != "detail":
                        continue
                    value = kw.value
                    if isinstance(value, ast.Dict):
                        value = next(
                            (
                                v
                                for k, v in zip(value.keys, value.values)
                                if _literal_text(k) == "message"
                            ),
                            None,
                        )
                    if value is not None and _is_raw_text(value):
                        raw.append(f"{path.name}:{node.lineno}")
            elif name == "ValueError" and node.args and _is_raw_text(node.args[0]):
                raw.append(f"{path.name}:{node.lineno}")
    assert not raw, "localized ile sarılmamış metinler:\n" + "\n".join(raw)


def test_degiskenle_cevrilen_metinlerin_ingilizcesi_var():
    """Sabit ya da değişkenle `localized`'a giden metinler (taramaya girmez)."""
    sources = [
        auth.SUSPENDED_DETAIL,
        auth.STUDENT_EMAIL_ERROR,
        moderation.SYSTEM_MARKER_REJECTION,
        *moderation._MESSAGES.values(),
        *listings._FIELD_LABELS.values(),
        "Metinde",
        "İçerikte",
        "Yorumda",
        "askıya alamazsın",
        "silemezsin",
        # transit.py'nin ürettiği, /api/alternatives'te çevrilen metin.
        "Mahalle bulunamadı.",
    ]
    assert [s for s in sources if s not in EN] == []


def test_transit_metinleri_sozlukle_ayni():
    """transit.py'deki metin değişirse sözlükteki anahtar da değişmeli."""
    source = (APP_DIR / "transit.py").read_text(encoding="utf-8")
    assert '"Mahalle bulunamadı."' in source


# ---- uçtan uca ----


def test_hata_mesaji_basliga_gore_dil_degistirir(client):
    tr = client.get("/api/listings/999999")
    en = client.get("/api/listings/999999", headers=EN_HEADERS)
    browser = client.get(
        "/api/listings/999999", headers={"Accept-Language": "en-US,en;q=0.9"}
    )

    assert tr.status_code == en.status_code == 404
    assert tr.json()["detail"] == "İlan bulunamadı."
    assert en.json()["detail"] == "Listing not found."
    assert browser.json()["detail"] == "Listing not found."


def test_hata_yanitinda_vary_basligi(client):
    res = client.get("/api/listings/999999", headers=EN_HEADERS)
    vary = ", ".join(res.headers.get_list("vary")).lower()
    assert "accept-language" in vary


def test_basarili_yanitta_vary_eklenmez(client):
    res = client.get("/api/listings", headers=EN_HEADERS)
    assert res.status_code == 200
    vary = ", ".join(res.headers.get_list("vary")).lower()
    assert "accept-language" not in vary


def test_bagimlilik_hatasi_da_cevrilir(client):
    # get_current_user eşzamanlı bir bağımlılık: iş parçacığı havuzunda
    # koşar, dil yine de oraya taşınmalı.
    res = client.post("/api/listings", json=EV_ILANI, headers=EN_HEADERS)
    assert res.status_code == 401
    assert res.json()["detail"] == "You need to sign in."


def test_dogrulayici_hatasi_da_cevrilir(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "ali@gmail.com", "password": "Sifre1234"},
        headers=EN_HEADERS,
    )
    assert res.status_code == 422
    assert "Only university email addresses (.edu.tr) can sign up." in res.text


def test_denetim_reddi_cevrilir(client):
    headers = _auth_headers(client)

    res = client.post(
        "/api/listings",
        json=EV_ILANI | {"title": "siktir git"},
        headers=headers | EN_HEADERS,
    )

    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["field"] == "title"
    assert detail["message"] == (
        "The title contains profanity or a serious insult. "
        "Edit this field and try again."
    )


def test_denetim_reddi_turkce_degismedi(client):
    headers = _auth_headers(client)

    res = client.post(
        "/api/listings", json=EV_ILANI | {"title": "siktir git"}, headers=headers
    )

    assert res.json()["detail"]["message"] == (
        "Başlıkta küfür veya ağır hakaret tespit edildi. "
        "Bu alanı düzenleyip tekrar deneyin."
    )


def test_hiz_siniri_mesaji_cevrilir(client):
    for _ in range(auth.RATE_LIMIT):
        client.post(
            "/api/auth/login",
            json={"email": "yok@uni.edu.tr", "password": "Yanlis1234"},
        )
    res = client.post(
        "/api/auth/login",
        json={"email": "yok@uni.edu.tr", "password": "Yanlis1234"},
        headers=EN_HEADERS,
    )
    assert res.status_code == 429
    assert res.json()["detail"] == "Too many attempts. Try again in 15 minutes."


def test_govde_siniri_413_cevrilir(client):
    node = app.middleware_stack
    while not isinstance(node, main_module.BodySizeLimitMiddleware):
        node = node.app
    original = node.max_bytes
    node.max_bytes = 1024
    try:
        res = client.post("/api/listings", content=b"y" * 5000, headers=EN_HEADERS)
    finally:
        node.max_bytes = original
    assert res.status_code == 413
    assert res.json()["detail"] == "Request body is too large."
