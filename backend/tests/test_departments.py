"""Bölüm listesi ve doğrulaması."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.departments import ALL_DEPARTMENTS, DEPARTMENT_GROUPS, is_valid
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


def _headers(client):
    res = client.post(
        "/api/auth/register",
        json={"email": "ali@uni.edu.tr", "password": "Sifre1234"},
    )
    token = client.post(
        "/api/auth/verify-otp",
        json={"email": "ali@uni.edu.tr", "code": res.json()["dev_code"]},
    ).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_is_sane():
    assert len(ALL_DEPARTMENTS) > 150
    assert "Bilgisayar Mühendisliği" in ALL_DEPARTMENTS
    assert "Psikoloji" in ALL_DEPARTMENTS
    # Gruplar içinde tekrar olmamalı
    flat = [d for names in DEPARTMENT_GROUPS.values() for d in names]
    assert len(flat) == len(set(flat))


def test_is_valid():
    assert is_valid(None) is True          # boş bırakmak serbest
    assert is_valid("Hukuk") is True
    assert is_valid("AlbionDepartment") is False


def test_endpoint_returns_groups(client):
    res = client.get("/api/auth/departments")
    assert res.status_code == 200
    data = res.json()
    assert "Mühendislik" in data
    assert "Bilgisayar Mühendisliği" in data["Mühendislik"]


def test_patch_rejects_unknown_department(client):
    headers = _headers(client)
    ok = client.patch("/api/auth/me", headers=headers, json={"department": "Hukuk"})
    assert ok.status_code == 200
    assert ok.json()["department"] == "Hukuk"

    bad = client.patch(
        "/api/auth/me", headers=headers, json={"department": "Uydurma Bölüm"}
    )
    assert bad.status_code == 422
