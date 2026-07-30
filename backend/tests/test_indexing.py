"""TÜFE endeks çarpanı testleri."""

import pytest

from app import indexing
from app.indexing import rent_index


def test_factor_is_cumulative_product(monkeypatch):
    monkeypatch.delenv("RENT_INDEX_FACTOR", raising=False)
    factor, indexed_to = rent_index()

    expected = 1.0
    for month, pct in indexing.MONTHLY_CPI.items():
        if month > indexing.DATA_PERIOD:
            expected *= 1 + pct / 100

    assert factor == pytest.approx(expected)
    assert indexed_to == max(indexing.MONTHLY_CPI)
    # 2026 Şub-Haz kümülatifi %10-15 bandında olmalı; tabloya yanlış birim
    # (ör. yıllık oran) girilirse bu test yakalar.
    assert 1.05 < factor < 1.20


def test_env_override(monkeypatch):
    monkeypatch.setenv("RENT_INDEX_FACTOR", "1.5")
    factor, indexed_to = rent_index()
    assert factor == 1.5
    assert indexed_to == "manuel"


def test_months_before_data_period_ignored(monkeypatch):
    monkeypatch.delenv("RENT_INDEX_FACTOR", raising=False)
    monkeypatch.setattr(indexing, "MONTHLY_CPI", {"2025-12": 99.0, "2026-02": 10.0})
    factor, indexed_to = rent_index()
    assert factor == pytest.approx(1.10)
    assert indexed_to == "2026-02"
