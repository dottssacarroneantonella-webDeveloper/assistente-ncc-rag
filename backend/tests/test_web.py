from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def site(settings, tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Assistente</title><div id=root></div>")
    (dist / "assets" / "index-abc123.js").write_text("console.log('ok')")
    (dist / "favicon.svg").write_text("<svg/>")
    (tmp_path / "segreto.txt").write_text("non leggibile")
    with TestClient(create_app(settings.model_copy(update={"static_dir": dist}))) as client:
        yield client


def test_index_with_frontend_csp(site) -> None:
    response = site.get("/")
    assert response.status_code == 200 and "Assistente" in response.text
    csp = response.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response.headers["Cache-Control"] == "no-cache"


def test_client_side_routes_fall_back_to_index(site) -> None:
    for path in ("/admin/documenti", "/privacy", "/admin/conversazioni/123"):
        response = site.get(path)
        assert response.status_code == 200 and "Assistente" in response.text, path


def test_hashed_assets_are_cached(site) -> None:
    response = site.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["Cache-Control"]
    assert site.get("/favicon.svg").status_code == 200


def test_api_routes_win_and_unknown_api_is_json_404(site) -> None:
    assert site.get("/api/v1/health").json()["status"] == "ok"
    missing = site.get("/api/v1/non-esiste")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_no_path_traversal(site) -> None:
    response = site.get("/..%2Fsegreto.txt")
    assert "non leggibile" not in response.text


def test_missing_index_fails_fast(settings, tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="index.html"):
        create_app(settings.model_copy(update={"static_dir": tmp_path}))
