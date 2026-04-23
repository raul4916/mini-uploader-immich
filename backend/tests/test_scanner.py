import httpx
import pytest
import respx

from app import scanner


def _fake_clamd_class(result):
    class _Fake:
        def __init__(self, *a, **kw):
            pass

        def instream(self, fh):
            return {"stream": result}

    return _Fake


@pytest.mark.asyncio
async def test_clamav_clean(tmp_path, monkeypatch):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    import clamd

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _fake_clamd_class(("OK", None)))
    await scanner.scan(f)  # no exception


@pytest.mark.asyncio
async def test_clamav_found(tmp_path, monkeypatch):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")
    import clamd

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _fake_clamd_class(("FOUND", "Win.Trojan.Test-1")))
    with pytest.raises(scanner.MalwareFound) as ei:
        await scanner.scan(f)
    assert ei.value.signature == "Win.Trojan.Test-1"


@pytest.mark.asyncio
async def test_scanner_unavailable_without_vt(tmp_path, monkeypatch):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")

    def _boom(*a, **kw):
        raise ConnectionRefusedError("nope")

    import clamd

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _boom)
    monkeypatch.setattr(scanner.settings, "vt_api_key", "")

    with pytest.raises(scanner.ScannerUnavailable):
        await scanner.scan(f)


@pytest.mark.asyncio
@respx.mock
async def test_vt_fallback_clean(tmp_path, monkeypatch):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")

    def _boom(*a, **kw):
        raise ConnectionRefusedError("nope")

    import clamd

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _boom)
    monkeypatch.setattr(scanner.settings, "vt_api_key", "vt-key")
    # Shorten polling wait
    import asyncio as _asyncio

    real_sleep = _asyncio.sleep

    async def _fast_sleep(_):
        await real_sleep(0)

    monkeypatch.setattr(scanner.asyncio, "sleep", _fast_sleep)

    respx.post("https://www.virustotal.com/api/v3/files").mock(
        return_value=httpx.Response(200, json={"data": {"id": "analysis-1"}})
    )
    respx.get("https://www.virustotal.com/api/v3/analyses/analysis-1").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"attributes": {"status": "completed", "stats": {"malicious": 0}, "results": {}}}},
        )
    )
    await scanner.scan(f)


@pytest.mark.asyncio
@respx.mock
async def test_vt_fallback_malicious(tmp_path, monkeypatch):
    f = tmp_path / "a.bin"
    f.write_bytes(b"hello")

    def _boom(*a, **kw):
        raise ConnectionRefusedError("nope")

    import clamd

    monkeypatch.setattr(clamd, "ClamdNetworkSocket", _boom)
    monkeypatch.setattr(scanner.settings, "vt_api_key", "vt-key")
    import asyncio as _asyncio

    real_sleep = _asyncio.sleep

    async def _fast_sleep(_):
        await real_sleep(0)

    monkeypatch.setattr(scanner.asyncio, "sleep", _fast_sleep)

    respx.post("https://www.virustotal.com/api/v3/files").mock(
        return_value=httpx.Response(200, json={"data": {"id": "analysis-1"}})
    )
    respx.get("https://www.virustotal.com/api/v3/analyses/analysis-1").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "status": "completed",
                        "stats": {"malicious": 3},
                        "results": {"EngineA": {"category": "malicious", "result": "Trojan.Gen"}},
                    }
                }
            },
        )
    )

    with pytest.raises(scanner.MalwareFound) as ei:
        await scanner.scan(f)
    assert "Trojan.Gen" in ei.value.signature
