"""Transfer budgets and HTTP semantics for the actual static route."""

import gzip
from pathlib import Path

import pytest
from flask import Flask

from liga_maestros.routes.main import bp


@pytest.fixture
def client():
    app = Flask(__name__, static_folder=None)
    app.register_blueprint(bp)
    return app.test_client()


@pytest.mark.parametrize("asset", ["css/kawaii.css", "js/pages/cover_page.js", "js/quantum_final.js"])
def test_gzip_reduces_transfer_without_changing_content(client, asset):
    plain = client.get(f"/static/{asset}?v=test")
    packed = client.get(f"/static/{asset}?v=test", headers={"Accept-Encoding": "gzip"})
    assert packed.status_code == 200
    assert packed.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in plain.headers["Vary"]
    assert "Accept-Encoding" in packed.headers["Vary"]
    assert packed.mimetype == plain.mimetype
    assert gzip.decompress(packed.data) == plain.data
    assert len(packed.data) < len(plain.data) * 0.4
    assert packed.headers["Cache-Control"] == plain.headers["Cache-Control"]


def test_gzip_has_own_etag_and_supports_revalidation(client):
    url = "/static/css/kawaii.css?v=test"
    plain = client.get(url)
    packed = client.get(url, headers={"Accept-Encoding": "gzip"})
    assert packed.headers["ETag"] != plain.headers["ETag"]
    cached = client.get(url, headers={"Accept-Encoding": "gzip", "If-None-Match": packed.headers["ETag"]})
    assert cached.status_code == 304
    assert cached.data == b""
    assert "Accept-Encoding" in cached.headers["Vary"]
    assert client.get(url, headers={"If-None-Match": packed.headers["ETag"]}).status_code == 200


def test_head_and_range_remain_supported(client):
    url = "/static/css/kawaii.css"
    packed = client.get(url, headers={"Accept-Encoding": "gzip"})
    head = client.head(url, headers={"Accept-Encoding": "gzip"})
    assert head.data == b""
    assert head.headers["Content-Length"] == packed.headers["Content-Length"]
    partial = client.get(url, headers={"Accept-Encoding": "gzip", "Range": "bytes=0-9"})
    assert partial.status_code == 206
    assert "Content-Encoding" not in partial.headers
    assert len(partial.data) == 10


def test_disabled_gzip_and_binary_assets_are_not_compressed(client):
    response = client.get("/static/css/kawaii.css", headers={"Accept-Encoding": "gzip;q=0"})
    assert "Content-Encoding" not in response.headers
    image = client.get("/static/img/ligademaestroslogo_trans.png", headers={"Accept-Encoding": "gzip"})
    assert image.status_code == 200
    assert "Content-Encoding" not in image.headers


def test_view_download_is_part_of_parallel_initial_requests():
    source = (Path(__file__).resolve().parents[1] / "static/js/quantum_final.js").read_text()
    refresh = source.split("async function refreshData(options = {})", 1)[1].split("// Un solo detalle", 1)[0]
    parallel = refresh.split("await Promise.all([", 1)[1].split("]);", 1)[0]
    assert "ensureViewAssets(currentMainView())" in parallel
    assert "await ensureViewAssets" not in refresh
