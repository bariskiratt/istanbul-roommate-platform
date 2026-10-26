"""Lambda servisinin testleri: backend'in pricing.py'si imajdaki gibi `app` paketi."""

import os
import sys
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
REPO = SERVICE.parents[1]
sys.path[:0] = [str(SERVICE), str(REPO / "backend")]

# handler import edilirken modeli önceden yüklemeye çalışır; testler kendi
# modelini verir.
for name in ("MODEL_PATH", "MODEL_VERSION", "MODEL_SHA256", "MODEL_BUCKET"):
    os.environ.pop(name, None)
