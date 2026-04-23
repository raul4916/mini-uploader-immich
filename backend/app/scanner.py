import asyncio
import socket
from pathlib import Path

import httpx

from .config import settings


class MalwareFound(Exception):
    def __init__(self, signature: str):
        super().__init__(signature)
        self.signature = signature


class ScannerUnavailable(Exception):
    pass


def _clamav_scan(path: Path) -> tuple[str, str | None]:
    import clamd  # type: ignore

    cd = clamd.ClamdNetworkSocket(host=settings.clamd_host, port=settings.clamd_port, timeout=30)
    with path.open("rb") as fh:
        result = cd.instream(fh)
    # result = {"stream": ("OK", None)} or {"stream": ("FOUND", "Sig.Name")}
    status, sig = result["stream"]
    return status, sig


async def _vt_scan(path: Path) -> tuple[str, str | None]:
    if not settings.vt_api_key:
        raise ScannerUnavailable("VT API key not set")
    headers = {"x-apikey": settings.vt_api_key}
    async with httpx.AsyncClient(base_url="https://www.virustotal.com/api/v3", headers=headers, timeout=120.0) as c:
        with path.open("rb") as fh:
            files = {"file": (path.name, fh)}
            r = await c.post("/files", files=files)
        if r.status_code != 200:
            raise ScannerUnavailable(f"VT upload {r.status_code}: {r.text[:200]}")
        analysis_id = r.json()["data"]["id"]
        # Poll up to ~60s
        for _ in range(20):
            await asyncio.sleep(3)
            a = await c.get(f"/analyses/{analysis_id}")
            if a.status_code != 200:
                continue
            body = a.json()
            attrs = body.get("data", {}).get("attributes", {})
            if attrs.get("status") == "completed":
                stats = attrs.get("stats", {})
                malicious = int(stats.get("malicious", 0))
                if malicious > 0:
                    # Find a signature name
                    results = attrs.get("results", {})
                    sig = next(
                        (v.get("result") for v in results.values() if v.get("category") == "malicious" and v.get("result")),
                        "VT:malicious",
                    )
                    return "FOUND", sig
                return "OK", None
        raise ScannerUnavailable("VT analysis timeout")


async def scan(path: Path) -> None:
    """Raise MalwareFound or ScannerUnavailable. Return None on clean."""
    # Try ClamAV in a thread (clamd lib is sync).
    try:
        status, sig = await asyncio.to_thread(_clamav_scan, path)
        if status == "FOUND":
            raise MalwareFound(sig or "unknown")
        return
    except MalwareFound:
        raise
    except (ConnectionRefusedError, socket.error, OSError, ImportError, Exception) as e:
        # clamd raises its own ConnectionError — catch broadly, fall through to VT.
        clamav_err = e
    # Fallback to VT
    try:
        status, sig = await _vt_scan(path)
    except ScannerUnavailable:
        raise ScannerUnavailable(f"clamav unavailable ({clamav_err}); VT unavailable or not configured")
    if status == "FOUND":
        raise MalwareFound(sig or "unknown")
