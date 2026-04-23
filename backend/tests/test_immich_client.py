import httpx
import pytest
import respx

from app import immich


@pytest.mark.asyncio
@respx.mock
async def test_ping_ok():
    respx.get("http://immich.local/api/server/ping").mock(return_value=httpx.Response(200, json={"res": "pong"}))
    assert await immich.ping("http://immich.local", "k") is True


@pytest.mark.asyncio
@respx.mock
async def test_ping_false_on_non_200():
    respx.get("http://immich.local/api/server/ping").mock(return_value=httpx.Response(500))
    assert await immich.ping("http://immich.local", "k") is False


@pytest.mark.asyncio
@respx.mock
async def test_list_albums_ok():
    respx.get("http://immich.local/api/albums").mock(
        return_value=httpx.Response(200, json=[{"id": "a1", "albumName": "One"}, {"id": "a2", "albumName": "Two"}])
    )
    out = await immich.list_albums("http://immich.local", "k")
    assert out == [{"id": "a1", "albumName": "One"}, {"id": "a2", "albumName": "Two"}]


@pytest.mark.asyncio
@respx.mock
async def test_list_albums_error():
    respx.get("http://immich.local/api/albums").mock(return_value=httpx.Response(401, text="nope"))
    with pytest.raises(immich.ImmichError):
        await immich.list_albums("http://immich.local", "k")


@pytest.mark.asyncio
@respx.mock
async def test_get_album_ok():
    respx.get("http://immich.local/api/albums/abc").mock(
        return_value=httpx.Response(200, json={"id": "abc", "albumName": "X"})
    )
    out = await immich.get_album("http://immich.local", "k", "abc")
    assert out["albumName"] == "X"


@pytest.mark.asyncio
@respx.mock
async def test_upload_asset_sends_headers_and_returns_id(tmp_path):
    route = respx.post("http://immich.local/api/assets").mock(
        return_value=httpx.Response(201, json={"id": "asset-xyz"})
    )
    f = tmp_path / "a.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n")
    out = await immich.upload_asset(
        "http://immich.local", "mykey", f, "dev-1", "image/png",
        "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"
    )
    assert out == "asset-xyz"
    sent = route.calls.last.request
    assert sent.headers["x-api-key"] == "mykey"


@pytest.mark.asyncio
@respx.mock
async def test_upload_asset_failure():
    respx.post("http://immich.local/api/assets").mock(return_value=httpx.Response(500, text="boom"))
    import tempfile
    from pathlib import Path

    f = Path(tempfile.mkstemp(suffix=".png")[1])
    f.write_bytes(b"x")
    with pytest.raises(immich.ImmichError):
        await immich.upload_asset(
            "http://immich.local", "k", f, "d", "image/png", "t", "t"
        )


@pytest.mark.asyncio
@respx.mock
async def test_add_to_album_ok():
    respx.put("http://immich.local/api/albums/abc/assets").mock(
        return_value=httpx.Response(200, json=[{"id": "x", "success": True}])
    )
    await immich.add_to_album("http://immich.local", "k", "abc", "x")


@pytest.mark.asyncio
@respx.mock
async def test_add_to_album_error():
    respx.put("http://immich.local/api/albums/abc/assets").mock(return_value=httpx.Response(400))
    with pytest.raises(immich.ImmichError):
        await immich.add_to_album("http://immich.local", "k", "abc", "x")
