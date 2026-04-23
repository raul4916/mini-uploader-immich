import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .. import auth, db, immich
from ..auth import require_admin, verify_password
from ..config import settings
from ..crypto import decrypt, encrypt

router = APIRouter(prefix="/api/admin", tags=["admin"])


class LoginIn(BaseModel):
    username: str
    password: str


class SetupIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=256)


class ChangePasswordIn(BaseModel):
    current: str
    new: str = Field(..., min_length=8, max_length=256)


class ConfigIn(BaseModel):
    immich_url: str = Field(..., min_length=1)
    immich_api_key: str | None = None  # optional — reuse stored if omitted
    album_id: str = Field(..., min_length=1)
    album_name: str | None = None


class ConfigOut(BaseModel):
    immich_url: str | None
    album_id: str | None
    album_name: str | None
    api_key_set: bool
    upload_token: str | None
    upload_url: str | None
    token_rotated_at: str | None


def _current_api_key() -> str | None:
    enc = db.get("immich_api_key_enc")
    return decrypt(enc) if enc else None


@router.get("/setup/needed")
def setup_needed():
    return {"setup_needed": not auth.has_admin()}


@router.post("/setup")
def setup(payload: SetupIn, request: Request):
    if auth.has_admin():
        raise HTTPException(status_code=409, detail="admin already exists")
    try:
        auth.create_admin(payload.username, payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    request.session["admin"] = True
    return {"ok": True}


@router.post("/login")
def login(payload: LoginIn, request: Request):
    if not auth.has_admin():
        raise HTTPException(status_code=409, detail="setup required")
    if not verify_password(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    request.session["admin"] = True
    return {"ok": True}


@router.post("/password", dependencies=[Depends(require_admin)])
def change_password(payload: ChangePasswordIn):
    try:
        auth.change_password(payload.current, payload.new)
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    return {"admin": bool(request.session.get("admin"))}


@router.get("/config", response_model=ConfigOut, dependencies=[Depends(require_admin)])
def get_config():
    token = db.get("upload_token")
    return ConfigOut(
        immich_url=db.get("immich_url"),
        album_id=db.get("album_id"),
        album_name=db.get("album_name"),
        api_key_set=bool(db.get("immich_api_key_enc")),
        upload_token=token,
        upload_url=f"{settings.public_base_url.rstrip('/')}/u/{token}" if token else None,
        token_rotated_at=db.get("token_rotated_at"),
    )


@router.put("/config", response_model=ConfigOut, dependencies=[Depends(require_admin)])
async def put_config(payload: ConfigIn):
    api_key = payload.immich_api_key or _current_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required on first save")

    try:
        ok = await immich.ping(payload.immich_url, api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"immich unreachable: {e}")
    if not ok:
        raise HTTPException(status_code=400, detail="immich ping failed")

    try:
        album = await immich.get_album(payload.immich_url, api_key, payload.album_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"album not found: {e}")

    db.set_("immich_url", payload.immich_url.rstrip("/"))
    db.set_("album_id", payload.album_id)
    db.set_("album_name", payload.album_name or album.get("albumName", ""))
    if payload.immich_api_key:
        db.set_("immich_api_key_enc", encrypt(payload.immich_api_key))

    return get_config()


class AlbumProbeIn(BaseModel):
    immich_url: str
    immich_api_key: str | None = None


@router.post("/albums", dependencies=[Depends(require_admin)])
async def list_albums(payload: AlbumProbeIn):
    api_key = payload.immich_api_key or _current_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="api_key required")
    try:
        return await immich.list_albums(payload.immich_url, api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"{e}")


@router.post("/token/rotate", dependencies=[Depends(require_admin)])
def rotate_token():
    token = secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    db.set_("upload_token", token)
    db.set_("token_rotated_at", now)
    return {
        "upload_token": token,
        "upload_url": f"{settings.public_base_url.rstrip('/')}/u/{token}",
        "token_rotated_at": now,
    }
