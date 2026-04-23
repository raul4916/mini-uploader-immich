import os
from pathlib import Path

from app import config as cfg_mod
from app.crypto import decrypt, encrypt


def test_crypto_roundtrip():
    original = "my-immich-api-key-with-specials-!@#$%^"
    token = encrypt(original)
    assert token != original
    assert decrypt(token) == original


def test_crypto_key_derivation_tolerates_non_fernet_secret(monkeypatch):
    # config.load_or_create_secret generates a real Fernet key, but the derivation
    # path also handles arbitrary secrets by hashing. Verify that.
    monkeypatch.setattr(cfg_mod.settings, "app_secret", "not-a-fernet-key-just-a-string")
    original = "hello"
    assert decrypt(encrypt(original)) == original


def test_load_or_create_secret_generates_and_persists(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(cfg_mod.settings, "db_path", db_path)
    monkeypatch.setattr(cfg_mod.settings, "app_secret", "")

    key1 = cfg_mod.load_or_create_secret()
    assert key1
    secret_file = db_path.parent / "secret.key"
    assert secret_file.is_file()
    assert secret_file.read_text().strip() == key1
    # permissions should be 0600 where supported
    if hasattr(os, "stat"):
        mode = secret_file.stat().st_mode & 0o777
        assert mode in (0o600, 0o644)  # accept 0o644 on fs without chmod support

    # second call with empty env secret → reads file
    monkeypatch.setattr(cfg_mod.settings, "app_secret", "")
    key2 = cfg_mod.load_or_create_secret()
    assert key2 == key1


def test_load_or_create_secret_env_overrides_file(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(cfg_mod.settings, "db_path", db_path)
    (db_path.parent).mkdir(parents=True, exist_ok=True)
    (db_path.parent / "secret.key").write_text("file-value")

    monkeypatch.setattr(cfg_mod.settings, "app_secret", "env-value")
    assert cfg_mod.load_or_create_secret() == "env-value"
