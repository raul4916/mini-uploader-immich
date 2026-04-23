import os
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Optional env override. If unset, a key is generated on first run and
    # persisted to data/secret.key.
    app_secret: str = ""

    clamd_host: str = "localhost"
    clamd_port: int = 3310
    vt_api_key: str = ""

    db_path: Path = Path("./data/app.db")
    max_upload_mb: int = 50
    public_base_url: str = "http://localhost:8000"


settings = Settings()


def _secret_file() -> Path:
    return settings.db_path.parent / "secret.key"


def load_or_create_secret() -> str:
    """Return APP_SECRET: env override, else persisted file, else freshly generated."""
    if settings.app_secret:
        return settings.app_secret
    path = _secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        settings.app_secret = path.read_text().strip()
        return settings.app_secret
    key = Fernet.generate_key().decode()
    path.write_text(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    settings.app_secret = key
    return key


