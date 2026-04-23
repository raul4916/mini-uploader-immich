import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


def _key() -> bytes:
    raw = settings.app_secret.encode()
    # If user supplied a raw Fernet key (44 url-safe base64 chars), use as-is.
    # Otherwise derive one via sha256 → urlsafe b64.
    if len(raw) == 44:
        try:
            Fernet(raw)
            return raw
        except (ValueError, InvalidToken):
            pass
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt(plaintext: str) -> str:
    return Fernet(_key()).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return Fernet(_key()).decrypt(ciphertext.encode()).decode()
