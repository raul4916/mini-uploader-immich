"""Set up env + a fresh SQLite before any app module imports."""

import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

# These must be set before `app.*` imports so pydantic-settings picks them up.
_tmpdir = Path(tempfile.mkdtemp(prefix="mu_test_"))
os.environ["DB_PATH"] = str(_tmpdir / "test.db")
os.environ["APP_SECRET"] = Fernet.generate_key().decode()
os.environ["CLAMD_HOST"] = "127.0.0.1"
os.environ["CLAMD_PORT"] = "9999"  # nothing listens — scanner fallback tested separately
os.environ["VT_API_KEY"] = ""
os.environ["PUBLIC_BASE_URL"] = "http://test.local"
os.environ["MAX_UPLOAD_MB"] = "5"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db():
    """Blank the config table before every test so each test starts clean."""
    db.init_db()
    with db._conn() as c:  # type: ignore[attr-defined]
        c.execute("DELETE FROM config")
    yield


@pytest.fixture
def client():
    return TestClient(fastapi_app)


@pytest.fixture
def auth_client(client):
    """Client already set up + logged in as admin 'tester'."""
    r = client.post("/api/admin/setup", json={"username": "tester", "password": "password123"})
    assert r.status_code == 200
    return client


@pytest.fixture
def tmp_upload_dir(tmp_path: Path) -> Path:
    return tmp_path


def _configure_immich(auth_client: TestClient, monkeypatch) -> None:
    """Helper used by tests: mock Immich validation + save config."""
    from app import immich

    async def _ping(*a, **kw):
        return True

    async def _get_album(*a, **kw):
        return {"id": "album-1", "albumName": "Test Album"}

    monkeypatch.setattr(immich, "ping", _ping)
    monkeypatch.setattr(immich, "get_album", _get_album)

    r = auth_client.put(
        "/api/admin/config",
        json={
            "immich_url": "http://immich.local",
            "immich_api_key": "fake-api-key",
            "album_id": "album-1",
            "album_name": "Test Album",
        },
    )
    assert r.status_code == 200, r.text
