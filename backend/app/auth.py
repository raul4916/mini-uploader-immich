import bcrypt
from fastapi import HTTPException, Request, status

from . import db


def has_admin() -> bool:
    return bool(db.get("admin_user")) and bool(db.get("admin_pass_hash"))


def create_admin(username: str, password: str) -> None:
    if has_admin():
        raise RuntimeError("admin already exists")
    if not username or not password:
        raise ValueError("username and password required")
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    db.set_("admin_user", username)
    db.set_("admin_pass_hash", hashed)


def verify_password(username: str, password: str) -> bool:
    stored_user = db.get("admin_user")
    stored_hash = db.get("admin_pass_hash")
    if not stored_user or not stored_hash or username != stored_user:
        return False
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except ValueError:
        return False


def change_password(current: str, new: str) -> None:
    stored_user = db.get("admin_user") or ""
    if not verify_password(stored_user, current):
        raise PermissionError("current password wrong")
    if len(new) < 8:
        raise ValueError("password must be at least 8 characters")
    db.set_("admin_pass_hash", bcrypt.hashpw(new.encode(), bcrypt.gensalt()).decode())


def require_admin(request: Request) -> None:
    if not request.session.get("admin"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth required")
