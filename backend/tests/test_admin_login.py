"""Yönetici hesabının sıkılaştırılması.

Kapsam:
  - Yönetici girişi İKİ ADIMLI: şifre + e-posta kodu birlikte (app/auth.py)
  - Normal hesabın girişi DEĞİŞMEDİ (şifre ya da kod, biri yeter)
  - ADMIN_EMAILS yalnızca ortam değişkeninden gelir, varsayılanı yok;
    üretimde boşsa açılış durur (app/config.py::check_admin_emails)
  - Hesabın e-postası değiştirilemez: is_admin e-postaya bağlı olduğu için
    e-posta değişebilseydi herkes kendini yönetici yapabilirdi
  - /api/admin/* uçlarının HEPSİ require_admin'den geçer (router katmanı)
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth, config
from app.config import ADMIN_EMAILS
from app.db import Base, get_db
from app.main import app
from app.reports import require_admin

ADMIN_EMAIL = sorted(ADMIN_EMAILS)[0]
USER_EMAIL = "ali@uni.edu.tr"
PASSWORD = "Sifre1234"

BACKEND_DIR = Path(__file__).resolve().parent.parent


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


def _register_verified(client, email: str) -> dict:
    """Hesabı açıp doğrular (yöneticide şifre de gider); oturum gövdesini döner."""
    res = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert res.status_code == 201, res.text
    res = client.post(
        "/api/auth/verify-otp",
        json={"email": email, "code": res.json()["dev_code"], "password": PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _password_step(client, email: str = ADMIN_EMAIL) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return res.json()


# --------------------------------------------------------------------------
# Yönetici girişi: iki adım
# --------------------------------------------------------------------------


def test_admin_password_alone_opens_no_session(client):
    """Doğru şifre yöneticiye oturum AÇMAZ; e-postaya kod gönderir."""
    _register_verified(client, ADMIN_EMAIL)

    body = _password_step(client)

    assert "token" not in body
    assert body["otp_required"] is True
    assert body["detail"] == auth.ADMIN_CODE_SENT
    # conftest DEV_OTP=1 verir; kod yanıtta da döner.
    assert len(body["dev_code"]) == 6


def test_admin_password_then_code_opens_admin_session(client):
    _register_verified(client, ADMIN_EMAIL)
    code = _password_step(client)["dev_code"]

    res = client.post(
        "/api/auth/verify-otp",
        json={"email": ADMIN_EMAIL, "code": code, "password": PASSWORD},
    )

    assert res.status_code == 200, res.text
    token = res.json()["token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["is_admin"] is True
    summary = client.get(
        "/api/admin/summary", headers={"Authorization": f"Bearer {token}"}
    )
    assert summary.status_code == 200


def test_admin_code_alone_is_refused_but_not_spent(client):
    """Kod tek başına yetmez; şifre eklenince AYNI kod çalışır.

    Gelen kutusu ele geçirilmiş bir yönetici hesabının senaryosu: saldırgan
    /request-otp ile kodu alır ama şifreyi bilmeden paneli açamaz.
    """
    _register_verified(client, ADMIN_EMAIL)
    code = client.post(
        "/api/auth/request-otp", json={"email": ADMIN_EMAIL}
    ).json()["dev_code"]

    res = client.post("/api/auth/verify-otp", json={"email": ADMIN_EMAIL, "code": code})
    assert res.status_code == 401, res.text
    assert res.json()["detail"] == {
        "message": auth.ADMIN_PASSWORD_REQUIRED,
        "field": "password",
    }
    assert "token" not in res.json()

    res = client.post(
        "/api/auth/verify-otp",
        json={"email": ADMIN_EMAIL, "code": code, "password": PASSWORD},
    )
    assert res.status_code == 200, res.text


def test_admin_code_with_wrong_password_is_refused(client):
    _register_verified(client, ADMIN_EMAIL)
    code = _password_step(client)["dev_code"]

    res = client.post(
        "/api/auth/verify-otp",
        json={"email": ADMIN_EMAIL, "code": code, "password": "Yanlis9999"},
    )

    assert res.status_code == 401, res.text
    assert res.json()["detail"]["message"] == auth.ADMIN_PASSWORD_WRONG
    assert res.json()["detail"]["field"] == "password"


def test_admin_step_messages_follow_the_language(client):
    """İngilizce arayüzde ikinci adımın metinleri de İngilizce gelir."""
    _register_verified(client, ADMIN_EMAIL)
    en = {"Accept-Language": "en"}

    res = client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": PASSWORD},
        headers=en,
    )
    assert res.json()["detail"] == "Admin account: enter the code we just emailed you."

    res = client.post(
        "/api/auth/verify-otp",
        json={"email": ADMIN_EMAIL, "code": res.json()["dev_code"]},
        headers=en,
    )
    assert res.json()["detail"] == {
        "message": "Admin account: enter your password along with the code.",
        "field": "password",
    }


def test_wrong_code_does_not_reveal_an_admin_account(client):
    """Yanlış kodla gelen istek, adresin yönetici olduğunu ÖĞRENEMEZ.

    Şifre kontrolü kod doğrulandıktan SONRA çalışır; yanlış kodda yanıt normal
    hesaptakiyle birebir aynıdır. Yönetici adresleri artık repoda yazılı
    olmadığı için bu bilgi sızmamalı.
    """
    _register_verified(client, ADMIN_EMAIL)
    _register_verified(client, USER_EMAIL)
    for email in (ADMIN_EMAIL, USER_EMAIL):
        client.post("/api/auth/request-otp", json={"email": email})

    def wrong_code(email):
        res = client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
        return res.status_code, res.json()

    # 1/1.000.000 ihtimalle gerçek kod 000000 olabilir (test_auth ile aynı kabul).
    assert wrong_code(ADMIN_EMAIL) == wrong_code(USER_EMAIL) == (
        400,
        {"detail": "Kod hatalı."},
    )


def test_wrong_admin_password_is_still_a_plain_401(client):
    """Yanlış şifre yönetici hesabında da normal hesaptaki yanıtı alır."""
    _register_verified(client, ADMIN_EMAIL)
    res = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": "Yanlis9999"}
    )
    assert res.status_code == 401
    assert res.json() == {"detail": "E-posta veya şifre hatalı."}


def test_admin_login_mail_warns_about_a_leaked_password(client, monkeypatch):
    """Şifre adımının postası ayrıdır: istemeyen yönetici şifresinin sızdığını anlar."""
    _register_verified(client, ADMIN_EMAIL)
    sent = []

    def fake_send(to, code, *, admin_login=False):
        sent.append((to, admin_login))
        return True

    monkeypatch.setattr(auth, "send_otp_email", fake_send)

    _password_step(client)
    client.post("/api/auth/request-otp", json={"email": ADMIN_EMAIL})

    assert sent == [(ADMIN_EMAIL, True), (ADMIN_EMAIL, False)]


def test_admin_login_codes_are_rate_limited(client):
    """Şifreyi bilen biri de yöneticinin gelen kutusunu dolduramaz."""
    _register_verified(client, ADMIN_EMAIL)
    for _ in range(auth.ADMIN_LOGIN_OTP_LIMIT):
        _password_step(client)

    res = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    assert res.status_code == 429


def test_unverified_admin_needs_the_password_too(client):
    """İlk doğrulamada da (kayıt sonrası) yönetici kodu tek başına yetmez."""
    res = client.post(
        "/api/auth/register", json={"email": ADMIN_EMAIL, "password": PASSWORD}
    )
    code = res.json()["dev_code"]

    res = client.post("/api/auth/verify-otp", json={"email": ADMIN_EMAIL, "code": code})
    assert res.status_code == 401
    assert res.json()["detail"]["field"] == "password"


# --------------------------------------------------------------------------
# Normal hesap: davranış değişmedi
# --------------------------------------------------------------------------


def test_regular_user_still_signs_in_with_either_factor(client):
    _register_verified(client, USER_EMAIL)

    body = _password_step(client, USER_EMAIL)
    assert body["token"]
    assert body["user"]["is_admin"] is False

    code = client.post(
        "/api/auth/request-otp", json={"email": USER_EMAIL}
    ).json()["dev_code"]
    res = client.post("/api/auth/verify-otp", json={"email": USER_EMAIL, "code": code})
    assert res.status_code == 200, res.text
    assert res.json()["token"]


# --------------------------------------------------------------------------
# ADMIN_EMAILS: yalnızca ortam değişkeni
# --------------------------------------------------------------------------


def test_admin_emails_have_no_default():
    """Değişken tanımsızsa liste BOŞ: repoda hiçbir adres yönetici değil.

    Ayrı süreçte koşar, çünkü liste modül yüklenirken bir kez hesaplanır ve
    bu süreçte conftest onu zaten doldurdu.
    """
    env = {k: v for k, v in os.environ.items() if k != "ADMIN_EMAILS"}
    out = subprocess.run(
        [sys.executable, "-c", "from app import config; print(sorted(config.ADMIN_EMAILS))"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "[]"


def test_empty_admin_emails_stop_a_production_boot(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    with pytest.raises(RuntimeError, match="ADMIN_EMAILS"):
        config.check_admin_emails()


def test_empty_admin_emails_only_warn_locally(monkeypatch, capsys):
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    monkeypatch.delenv("DATABASE_URL", raising=False)
    config.check_admin_emails()
    assert "ADMIN_EMAILS" in capsys.readouterr().out


def test_set_admin_emails_pass_the_boot_check(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
    config.check_admin_emails()
    assert capsys.readouterr().out == ""


def test_admin_address_is_exempt_from_the_student_rule(client):
    """Yöneticinin öğrenci olmayan adresi de hesap açabilir (bkz. config)."""
    other = next(e for e in ADMIN_EMAILS if not auth.is_student_email(e))
    res = client.post("/api/auth/register", json={"email": other, "password": PASSWORD})
    assert res.status_code == 201, res.text
    res = client.post(
        "/api/auth/register", json={"email": "biri@gmail.com", "password": PASSWORD}
    )
    assert res.status_code == 422


# --------------------------------------------------------------------------
# E-posta değişmezliği
# --------------------------------------------------------------------------


def test_profile_update_cannot_change_the_email(client):
    """PATCH /me e-postayı değiştiremez — yoksa herkes kendini yönetici yapardı."""
    body = _register_verified(client, USER_EMAIL)
    headers = {"Authorization": f"Bearer {body['token']}"}

    res = client.patch("/api/auth/me", headers=headers, json={"email": ADMIN_EMAIL})

    assert res.status_code == 200, res.text
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == USER_EMAIL
    assert me["is_admin"] is False
    assert client.get("/api/admin/summary", headers=headers).status_code == 403


def test_no_schema_accepts_an_email_change():
    assert "email" not in auth.UserUpdate.model_fields


def test_app_code_never_assigns_a_users_email():
    """Uygulama kodunda `<nesne>.email = ...` ataması YOK.

    E-posta yalnızca hesap açılırken (models.User(email=...)) yazılır. Bu test
    ileride eklenecek bir "e-postanı değiştir" ucunun, yönetici yetkisinin
    e-postaya bağlı olduğu unutularak yazılmasını yakalar: böyle bir uç
    eklenirse yeni adresin doğrulanması ve is_admin'in yeniden düşünülmesi
    gerekir.
    """
    offenders = []
    for path in sorted((BACKEND_DIR / "app").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "email":
                    offenders.append(f"{path.name}:{node.lineno}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "setattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "email"
            ):
                offenders.append(f"{path.name}:{node.lineno}")
    assert offenders == []


# --------------------------------------------------------------------------
# /api/admin/*: router katmanında require_admin
# --------------------------------------------------------------------------


def _dependency_calls(dependant) -> set:
    calls = set()
    for dep in dependant.dependencies:
        calls.add(dep.call)
        calls |= _dependency_calls(dep)
    return calls


def _all_routes(routes):
    """Uygulamanın uçları; dahil edilmiş router'ların içine de iner.

    Yeni FastAPI sürümleri include_router'ı tembel bir sarmalayıcıyla
    (original_router) tutar, eskiler uçları düz listeye açar; ikisi de çalışır.
    """
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _all_routes(inner.routes)
        else:
            yield route


def test_every_admin_route_requires_admin():
    """Uç kendi parametresini unutsa da router onu require_admin'den geçirir."""
    admin_routes = [
        route
        for route in _all_routes(app.routes)
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin")
    ]
    assert len(admin_routes) >= 15
    for route in admin_routes:
        assert require_admin in _dependency_calls(route.dependant), route.path


def test_admin_router_itself_carries_the_dependency():
    from app.admin import router

    assert any(dep.dependency is require_admin for dep in router.dependencies)
