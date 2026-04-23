import io

from fastapi.testclient import TestClient

from app import immich, scanner
from app.main import app as fastapi_app

from .conftest import _configure_immich

# Minimal valid PNG (8 bytes signature + IHDR + IDAT + IEND) — 1x1 black pixel.
PNG_1PX = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _get_token(auth_client, monkeypatch) -> str:
    _configure_immich(auth_client, monkeypatch)
    r = auth_client.post("/api/admin/token/rotate")
    return r.json()["upload_token"]


def _mock_scanner_ok(monkeypatch):
    async def _scan(path):
        return None

    monkeypatch.setattr(scanner, "scan", _scan)


def _mock_immich_upload(monkeypatch, asset_id="asset-123"):
    async def _upload(*a, **kw):
        return asset_id

    async def _add(*a, **kw):
        return None

    monkeypatch.setattr(immich, "upload_asset", _upload)
    monkeypatch.setattr(immich, "add_to_album", _add)


def test_upload_rejects_unknown_token(auth_client, monkeypatch):
    _get_token(auth_client, monkeypatch)
    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": "nope"},
        files={"file": ("x.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 403


def test_upload_rejects_when_server_unconfigured(client):
    # setup admin but no Immich config
    client.post("/api/admin/setup", json={"username": "t", "password": "password123"})
    r = client.post("/api/admin/token/rotate")
    token = r.json()["upload_token"]

    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("x.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 503


def test_upload_rejects_wrong_mime(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)
    _mock_scanner_ok(monkeypatch)
    _mock_immich_upload(monkeypatch)

    fresh = TestClient(fastapi_app)
    # Fake SVG (disallowed) — but the server sniffs bytes, so send literal <svg>
    body = b"<svg xmlns='http://www.w3.org/2000/svg'><text>x</text></svg>"
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("x.svg", io.BytesIO(body), "image/svg+xml")},
    )
    assert r.status_code == 415


def test_upload_rejects_oversize(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)
    _mock_scanner_ok(monkeypatch)
    _mock_immich_upload(monkeypatch)

    fresh = TestClient(fastapi_app)
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (6 * 1024 * 1024)  # > MAX_UPLOAD_MB=5
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("big.png", io.BytesIO(big), "image/png")},
    )
    assert r.status_code == 413


def test_upload_malware_rejected(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)

    async def _scan(path):
        raise scanner.MalwareFound("Test.EICAR")

    monkeypatch.setattr(scanner, "scan", _scan)
    _mock_immich_upload(monkeypatch)

    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("x.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 422
    assert "Test.EICAR" in r.json()["detail"]


def test_upload_scanner_unavailable(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)

    async def _scan(path):
        raise scanner.ScannerUnavailable("no clamav, no VT")

    monkeypatch.setattr(scanner, "scan", _scan)
    _mock_immich_upload(monkeypatch)

    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("x.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 503


def test_upload_happy_path(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)
    _mock_scanner_ok(monkeypatch)

    seen: dict = {}

    async def _upload(base_url, api_key, path, device_asset_id, mime, created, modified):
        seen["base_url"] = base_url
        seen["api_key"] = api_key
        seen["mime"] = mime
        seen["device_asset_id"] = device_asset_id
        return "asset-abc"

    async def _add(base_url, api_key, album_id, asset_id):
        seen["album_id"] = album_id
        seen["asset_id"] = asset_id

    monkeypatch.setattr(immich, "upload_asset", _upload)
    monkeypatch.setattr(immich, "add_to_album", _add)

    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("pic.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["assetId"] == "asset-abc"
    assert body["mime"] == "image/png"
    assert seen["api_key"] == "fake-api-key"
    assert seen["album_id"] == "album-1"
    assert seen["asset_id"] == "asset-abc"


def test_upload_immich_failure_bubbles_as_502(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)
    _mock_scanner_ok(monkeypatch)

    async def _upload(*a, **kw):
        raise immich.ImmichError("500 internal")

    monkeypatch.setattr(immich, "upload_asset", _upload)

    fresh = TestClient(fastapi_app)
    r = fresh.post(
        "/api/upload",
        data={"token": token},
        files={"file": ("pic.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert r.status_code == 502


def test_upload_status_endpoint(auth_client, monkeypatch):
    token = _get_token(auth_client, monkeypatch)

    fresh = TestClient(fastapi_app)
    r = fresh.get(f"/api/upload/status/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["album_name"] == "Test Album"
    assert body["max_mb"] == 5

    assert fresh.get("/api/upload/status/bogus").status_code == 404
