from fastapi.testclient import TestClient

from app import immich
from app.main import app as fastapi_app

from .conftest import _configure_immich


def test_config_rejects_without_api_key_first_time(auth_client):
    r = auth_client.put(
        "/api/admin/config",
        json={"immich_url": "http://immich.local", "album_id": "album-1"},
    )
    assert r.status_code == 400


def test_config_rejects_immich_unreachable(auth_client, monkeypatch):
    async def _ping(*a, **kw):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(immich, "ping", _ping)

    r = auth_client.put(
        "/api/admin/config",
        json={
            "immich_url": "http://immich.local",
            "immich_api_key": "k",
            "album_id": "album-1",
        },
    )
    assert r.status_code == 400
    assert "immich" in r.json()["detail"].lower()


def test_config_save_and_reread(auth_client, monkeypatch):
    _configure_immich(auth_client, monkeypatch)

    cfg = auth_client.get("/api/admin/config").json()
    assert cfg["immich_url"] == "http://immich.local"
    assert cfg["album_id"] == "album-1"
    assert cfg["album_name"] == "Test Album"
    assert cfg["api_key_set"] is True
    assert cfg["upload_token"] is None


def test_config_api_key_not_round_tripped(auth_client, monkeypatch):
    _configure_immich(auth_client, monkeypatch)
    cfg = auth_client.get("/api/admin/config").json()
    # Full config response must NOT leak the key.
    assert "api_key" not in str(cfg).replace("api_key_set", "")
    assert "fake-api-key" not in str(cfg)


def test_config_api_key_persists_when_not_resent(auth_client, monkeypatch):
    _configure_immich(auth_client, monkeypatch)
    # Second save without api key should succeed using existing key.
    r = auth_client.put(
        "/api/admin/config",
        json={
            "immich_url": "http://immich.local",
            "album_id": "album-1",
            "album_name": "Test Album",
        },
    )
    assert r.status_code == 200


def test_list_albums(auth_client, monkeypatch):
    async def _list(*a, **kw):
        return [{"id": "a1", "albumName": "One"}, {"id": "a2", "albumName": "Two"}]

    monkeypatch.setattr(immich, "list_albums", _list)

    r = auth_client.post(
        "/api/admin/albums",
        json={"immich_url": "http://immich.local", "immich_api_key": "k"},
    )
    assert r.status_code == 200
    assert r.json() == [{"id": "a1", "albumName": "One"}, {"id": "a2", "albumName": "Two"}]


def test_list_albums_error(auth_client, monkeypatch):
    async def _list(*a, **kw):
        raise immich.ImmichError("boom")

    monkeypatch.setattr(immich, "list_albums", _list)

    r = auth_client.post(
        "/api/admin/albums",
        json={"immich_url": "http://immich.local", "immich_api_key": "k"},
    )
    assert r.status_code == 400


def test_token_rotate(auth_client, monkeypatch):
    _configure_immich(auth_client, monkeypatch)

    r = auth_client.post("/api/admin/token/rotate")
    assert r.status_code == 200
    body = r.json()
    assert body["upload_token"]
    assert body["upload_url"].startswith("http://test.local/u/")
    assert body["upload_url"].endswith(body["upload_token"])

    token1 = body["upload_token"]

    r2 = auth_client.post("/api/admin/token/rotate")
    token2 = r2.json()["upload_token"]
    assert token1 != token2  # new each call

    # /api/upload/status uses the fresh token
    fresh = TestClient(fastapi_app)
    assert fresh.get(f"/api/upload/status/{token2}").status_code == 200
    assert fresh.get(f"/api/upload/status/{token1}").status_code == 404
