def test_setup_needed_true_on_blank(client):
    r = client.get("/api/admin/setup/needed")
    assert r.status_code == 200
    assert r.json() == {"setup_needed": True}


def test_login_before_setup_is_409(client):
    r = client.post("/api/admin/login", json={"username": "x", "password": "password123"})
    assert r.status_code == 409


def test_setup_creates_admin_and_logs_in(client):
    r = client.post("/api/admin/setup", json={"username": "boss", "password": "password123"})
    assert r.status_code == 200
    # session cookie should be set; /me returns true
    me = client.get("/api/admin/me").json()
    assert me == {"admin": True}

    # setup/needed now false
    s = client.get("/api/admin/setup/needed").json()
    assert s == {"setup_needed": False}


def test_setup_rejects_short_password(client):
    r = client.post("/api/admin/setup", json={"username": "boss", "password": "short"})
    assert r.status_code == 422  # pydantic Field min_length


def test_setup_second_time_is_409(client):
    assert client.post("/api/admin/setup", json={"username": "a", "password": "password123"}).status_code == 200
    # new client w/o cookie should still see setup as complete
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    fresh = TestClient(fastapi_app)
    r = fresh.post("/api/admin/setup", json={"username": "b", "password": "password123"})
    assert r.status_code == 409


def test_login_wrong_password(client):
    client.post("/api/admin/setup", json={"username": "boss", "password": "password123"})
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    fresh = TestClient(fastapi_app)
    r = fresh.post("/api/admin/login", json={"username": "boss", "password": "WRONG"})
    assert r.status_code == 401


def test_login_roundtrip(client):
    client.post("/api/admin/setup", json={"username": "boss", "password": "password123"})
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    fresh = TestClient(fastapi_app)
    assert fresh.get("/api/admin/me").json() == {"admin": False}
    r = fresh.post("/api/admin/login", json={"username": "boss", "password": "password123"})
    assert r.status_code == 200
    assert fresh.get("/api/admin/me").json() == {"admin": True}
    fresh.post("/api/admin/logout")
    assert fresh.get("/api/admin/me").json() == {"admin": False}


def test_change_password(auth_client):
    # wrong current
    r = auth_client.post("/api/admin/password", json={"current": "WRONG", "new": "new_password_1"})
    assert r.status_code == 401

    # too short
    r = auth_client.post("/api/admin/password", json={"current": "password123", "new": "short"})
    assert r.status_code == 422

    # success
    r = auth_client.post("/api/admin/password", json={"current": "password123", "new": "new_password_1"})
    assert r.status_code == 200

    # can log in with new
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    fresh = TestClient(fastapi_app)
    assert fresh.post("/api/admin/login", json={"username": "tester", "password": "new_password_1"}).status_code == 200
    assert fresh.post("/api/admin/login", json={"username": "tester", "password": "password123"}).status_code == 401


def test_admin_endpoints_require_session(client):
    # no session → 401 on protected routes
    assert client.get("/api/admin/config").status_code == 401
    assert client.put("/api/admin/config", json={"immich_url": "x", "album_id": "y"}).status_code == 401
    assert client.post("/api/admin/token/rotate").status_code == 401
    assert client.post("/api/admin/albums", json={"immich_url": "x"}).status_code == 401
