"""Ev özellikleri ve "features" filtresi."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


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


def _auth_headers(client, email="ali@uni.edu.tr") -> dict:
    res = client.post(
        "/api/auth/register", json={"email": email, "password": "Sifre1234"}
    )
    code = res.json()["dev_code"]
    token = client.post(
        "/api/auth/verify-otp", json={"email": email, "code": code}
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _ev(**overrides) -> dict:
    return {
        "type": "ev_ilani",
        "title": "Kadıköy'de güneşli daire",
        "description": "Ulaşımı rahat, aydınlık bir ev.",
        "district": "Kadıköy",
        "photos": [],
        "rent": 18000,
        "room_count": "2+1",
    } | overrides


def test_ozellikler_kaydedilir_ve_donulur(client):
    headers = _auth_headers(client)
    res = client.post(
        "/api/listings",
        headers=headers,
        json=_ev(
            furnished=True,
            elevator=False,
            parking=True,
            internet_included=True,
            heating_included=False,
            balcony=True,
            natural_gas=True,
        ),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["furnished"] is True
    assert body["elevator"] is False
    assert body["natural_gas"] is True

    # Belirtilmeyen özellik None kalır (üç durumlu alan)
    res = client.post("/api/listings", headers=headers, json=_ev())
    assert res.json()["furnished"] is None


def test_ozellik_patch_ile_guncellenir(client):
    headers = _auth_headers(client)
    listing_id = client.post(
        "/api/listings", headers=headers, json=_ev(balcony=True)
    ).json()["id"]

    res = client.patch(
        f"/api/listings/{listing_id}",
        headers=headers,
        json={"furnished": True, "balcony": False},
    )
    assert res.status_code == 200, res.text
    assert res.json()["furnished"] is True
    assert res.json()["balcony"] is False


def test_features_filtresi_and_mantigi(client):
    headers = _auth_headers(client)
    # 1: ikisi de var  2: yalnız eşyalı  3: hiçbiri belirtilmemiş
    client.post(
        "/api/listings", headers=headers, json=_ev(furnished=True, balcony=True)
    )
    client.post(
        "/api/listings", headers=headers, json=_ev(furnished=True, balcony=False)
    )
    client.post("/api/listings", headers=headers, json=_ev())

    res = client.get("/api/listings", params={"features": "furnished,balcony"})
    assert res.status_code == 200, res.text
    assert [i["id"] for i in res.json()] == [1]

    # Tek özellik: belirtilmemiş (None) olan ilan eşleşmez
    res = client.get("/api/listings", params={"features": "furnished"})
    assert [i["id"] for i in res.json()] == [2, 1]

    # Boş değer filtre uygulamaz
    assert len(client.get("/api/listings", params={"features": ""}).json()) == 3


def test_features_diger_filtrelerle_birlesir(client):
    headers = _auth_headers(client)
    client.post(
        "/api/listings",
        headers=headers,
        json=_ev(district="Kadıköy", furnished=True),
    )
    client.post(
        "/api/listings",
        headers=headers,
        json=_ev(district="Beşiktaş", furnished=True),
    )

    res = client.get(
        "/api/listings", params={"features": "furnished", "district": "Beşiktaş"}
    )
    assert [i["id"] for i in res.json()] == [2]


def _kisisel(**overrides) -> dict:
    return {
        "type": "kisisel_ilan",
        "title": "Beşiktaş'ta ev arkadaşı arıyorum",
        "description": "3. sınıf öğrencisiyim, sakinim.",
        "district": "Beşiktaş",
        "photos": [],
        "budget_min": 8000,
        "budget_max": 14000,
    } | overrides


def test_ozellik_filtresi_kisisel_ilanlari_elemez(client):
    """Kişisel ilanların ev özelliği olamaz; filtre onları kapsam dışı bırakır.

    Aksi hâlde "asansörlü ev" arayan kullanıcı, ev arayan kişilerin ilanlarını
    da kaybediyordu — hiçbir kişisel ilan furnished=True olamayacağı için
    filtre desteyi ev ilanlarına indiriyordu.
    """
    headers = _auth_headers(client)
    ev_var = client.post(
        "/api/listings", headers=headers, json=_ev(furnished=True)
    ).json()["id"]
    ev_yok = client.post(
        "/api/listings", headers=headers, json=_ev(furnished=False)
    ).json()["id"]
    kisisel = client.post(
        "/api/listings", headers=headers, json=_kisisel()
    ).json()["id"]

    ids = [i["id"] for i in client.get(
        "/api/listings", params={"features": "furnished"}
    ).json()]
    assert kisisel in ids
    assert ev_var in ids
    assert ev_yok not in ids

    # type filtresiyle birleşince yine yalnız ev ilanları döner
    ids = [i["id"] for i in client.get(
        "/api/listings", params={"features": "furnished", "type": "ev_ilani"}
    ).json()]
    assert ids == [ev_var]


def test_coklu_ozellik_filtresi_kisisel_ilani_korur(client):
    headers = _auth_headers(client)
    client.post("/api/listings", headers=headers, json=_ev(furnished=True))
    kisisel = client.post(
        "/api/listings", headers=headers, json=_kisisel()
    ).json()["id"]

    ids = [i["id"] for i in client.get(
        "/api/listings", params={"features": "furnished,balcony,elevator"}
    ).json()]
    # Hiçbir ev ilanı üç koşulu birden sağlamıyor; kişisel ilan yine de durur
    assert ids == [kisisel]


def test_gecersiz_ozellik_422(client):
    res = client.get("/api/listings", params={"features": "furnished,havuz"})
    assert res.status_code == 422, res.text
    assert "havuz" in res.json()["detail"]
