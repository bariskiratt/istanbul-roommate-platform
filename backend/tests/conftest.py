"""Ortak test kurulumu."""

import pytest

from app import auth


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Bellek-içi hız limiti testler arasında taşınmasın."""
    auth._RATE_BUCKETS.clear()
    yield
    auth._RATE_BUCKETS.clear()
