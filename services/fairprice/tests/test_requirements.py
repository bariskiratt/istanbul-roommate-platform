"""Lambda imajı modeli eğiten taraftakiyle aynı kütüphane sürümlerini kurmalı.

Model joblib (pickle) ile saklanıyor: GitHub Actions'ta backend/requirements.txt
ile eğitiliyor, Lambda'da services/fairprice/requirements.txt ile açılıyor.
Biri yükseltilip diğeri unutulursa model ya hiç açılmaz ya da sessizce farklı
tahmin üretir (pricing.feature_signature bunu çalışma anında da yakalar; bu
test CI'da, birleştirmeden önce yakalar).
"""

import re
from pathlib import Path

from conftest import REPO, SERVICE

PIN = re.compile(r"^([A-Za-z0-9_.-]+)==([^\s;]+)", re.M)


def pins(path: Path) -> dict[str, str]:
    return {name.lower(): version for name, version in PIN.findall(path.read_text())}


def test_lambda_pins_match_backend():
    lambda_pins = pins(SERVICE / "requirements.txt")
    backend_pins = pins(REPO / "backend" / "requirements.txt")
    assert lambda_pins, "Lambda requirements.txt boş"
    mismatched = {
        name: (version, backend_pins.get(name))
        for name, version in lambda_pins.items()
        if backend_pins.get(name) != version
    }
    assert mismatched == {}, f"(lambda, backend) sürümleri ayrışmış: {mismatched}"


def test_model_libraries_are_pinned_for_lambda():
    from app.pricing import MODEL_LIBRARIES

    missing = set(MODEL_LIBRARIES) - set(pins(SERVICE / "requirements.txt"))
    assert missing == set()
