"""API belgesi (Swagger, ReDoc, OpenAPI şeması) varsayılan olarak kapalı.

Yayında herkese açıktı (docs/SECURITY.md L6). Artık yalnızca API_DOCS=1 ile
açılıyor; CI ve yayın bu değişkeni vermediği için burada kapalı hâli sınanır.
"""

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app

pytestmark = pytest.mark.skipif(
    config.API_DOCS,
    reason="API_DOCS=1 ile koşuluyor; kapalı varsayılanı sınamak için değişkeni kaldır",
)


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_pages_are_closed(path):
    assert TestClient(app).get(path).status_code == 404


def test_index_does_not_link_closed_docs():
    body = TestClient(app).get("/").json()
    assert body["name"] == "evdes.tr API"
    assert "docs" not in body
