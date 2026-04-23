from pathlib import Path

import httpx


class ImmichError(Exception):
    pass


def _client(base_url: str, api_key: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        headers={"x-api-key": api_key, "Accept": "application/json"},
        timeout=60.0,
    )


async def ping(base_url: str, api_key: str) -> bool:
    async with _client(base_url, api_key) as c:
        r = await c.get("/api/server/ping")
        return r.status_code == 200


async def list_albums(base_url: str, api_key: str) -> list[dict]:
    async with _client(base_url, api_key) as c:
        r = await c.get("/api/albums")
        if r.status_code != 200:
            raise ImmichError(f"list_albums {r.status_code}: {r.text[:200]}")
        return [{"id": a["id"], "albumName": a.get("albumName", "")} for a in r.json()]


async def get_album(base_url: str, api_key: str, album_id: str) -> dict:
    async with _client(base_url, api_key) as c:
        r = await c.get(f"/api/albums/{album_id}")
        if r.status_code != 200:
            raise ImmichError(f"get_album {r.status_code}")
        return r.json()


async def upload_asset(
    base_url: str,
    api_key: str,
    path: Path,
    device_asset_id: str,
    mime: str,
    created_at_iso: str,
    modified_at_iso: str,
) -> str:
    async with _client(base_url, api_key) as c:
        with path.open("rb") as fh:
            files = {"assetData": (path.name, fh, mime)}
            data = {
                "deviceAssetId": device_asset_id,
                "deviceId": "mini-uploader",
                "fileCreatedAt": created_at_iso,
                "fileModifiedAt": modified_at_iso,
                "isFavorite": "false",
            }
            r = await c.post("/api/assets", data=data, files=files)
        if r.status_code not in (200, 201):
            raise ImmichError(f"upload {r.status_code}: {r.text[:300]}")
        body = r.json()
        asset_id = body.get("id")
        if not asset_id:
            raise ImmichError(f"no id in response: {body}")
        return asset_id


async def add_to_album(base_url: str, api_key: str, album_id: str, asset_id: str) -> None:
    async with _client(base_url, api_key) as c:
        r = await c.put(f"/api/albums/{album_id}/assets", json={"ids": [asset_id]})
        if r.status_code not in (200, 201):
            raise ImmichError(f"add_to_album {r.status_code}: {r.text[:200]}")
