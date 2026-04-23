import hashlib
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .. import db, immich, scanner
from ..config import settings
from ..crypto import decrypt

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
    "image/gif",
}


def _mime_sniff(path: Path) -> str:
    try:
        import magic  # type: ignore

        return magic.from_file(str(path), mime=True)
    except Exception:
        # Tiny magic-byte fallback — don't trust client header.
        head = path.open("rb").read(12)
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
            return "image/gif"
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return "image/webp"
        if head[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypmsf1"):
            return "image/heic"
        return "application/octet-stream"


@router.post("/upload")
async def upload(file: UploadFile = File(...), token: str = Form(...)):
    stored = db.get("upload_token")
    if not stored or not secrets.compare_digest(stored, token):
        raise HTTPException(status_code=403, detail="invalid token")

    immich_url = db.get("immich_url")
    api_key_enc = db.get("immich_api_key_enc")
    album_id = db.get("album_id")
    if not (immich_url and api_key_enc and album_id):
        raise HTTPException(status_code=503, detail="server not configured")
    api_key = decrypt(api_key_enc)

    max_bytes = settings.max_upload_mb * 1024 * 1024
    suffix = Path(file.filename or "upload").suffix[:10]
    tmp = Path(tempfile.mkstemp(suffix=suffix)[1])

    try:
        # Stream to disk with size cap + hash.
        hasher = hashlib.sha256()
        total = 0
        with tmp.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail=f"file > {settings.max_upload_mb}MB")
                hasher.update(chunk)
                out.write(chunk)

        mime = _mime_sniff(tmp)
        if mime not in ALLOWED_MIME:
            raise HTTPException(status_code=415, detail=f"mime not allowed: {mime}")

        try:
            await scanner.scan(tmp)
        except scanner.MalwareFound as mf:
            raise HTTPException(status_code=422, detail=f"malware detected: {mf.signature}")
        except scanner.ScannerUnavailable as su:
            raise HTTPException(status_code=503, detail=f"scanner unavailable: {su}")

        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        device_asset_id = f"mini-uploader-{hasher.hexdigest()[:16]}"

        try:
            asset_id = await immich.upload_asset(
                immich_url, api_key, tmp, device_asset_id, mime, now_iso, now_iso
            )
            await immich.add_to_album(immich_url, api_key, album_id, asset_id)
        except immich.ImmichError as e:
            raise HTTPException(status_code=502, detail=f"immich: {e}")

        return {"ok": True, "assetId": asset_id, "bytes": total, "mime": mime}

    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@router.get("/upload/status/{token}")
def check_token(token: str):
    stored = db.get("upload_token")
    if not stored or not secrets.compare_digest(stored, token):
        raise HTTPException(status_code=404, detail="unknown token")
    return {
        "ok": True,
        "album_name": db.get("album_name"),
        "max_mb": settings.max_upload_mb,
    }
