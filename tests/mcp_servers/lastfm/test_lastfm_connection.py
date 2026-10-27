from unittest.mock import patch

import httpx
import pytest

from mcp_servers.lastfm_mcp.config.connections import lastfm_connection
from mcp_servers.lastfm_mcp.config.connections.lastfm_connection import LastFmConnect
from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError

SECRET = "chave-secreta-123"

@pytest.fixture(autouse=True)
def _settings():
    with patch.object(lastfm_connection, "LASTFM_API_KEY", SECRET), patch.object(
        lastfm_connection, "LASTFM_RETRY_BACKOFF_SECONDS", 0
    ):
        yield


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_request_sends_method_key_and_json_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"artist": {"name": "Radiohead"}})

    with patch.object(LastFmConnect, "_client_instance", return_value=_client(handler)):
        payload = await LastFmConnect.request("artist.getInfo", {"artist": "AC/DC&x=1"})

    assert payload == {"artist": {"name": "Radiohead"}}
    assert seen["method"] == "artist.getInfo"
    assert seen["api_key"] == SECRET
    assert seen["format"] == "json"
    assert seen["artist"] == "AC/DC&x=1"


@pytest.mark.asyncio
async def test_request_returns_none_when_resource_not_found():
    handler = lambda request: httpx.Response(404, json={"error": 6, "message": "Artist not found"})

    with patch.object(LastFmConnect, "_client_instance", return_value=_client(handler)):
        assert await LastFmConnect.request("artist.getInfo", {"artist": "x"}) is None


@pytest.mark.asyncio
async def test_request_raises_api_error_for_invalid_key_without_retrying():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(403, json={"error": 10, "message": "Invalid API key"})

    with patch.object(LastFmConnect, "_client_instance", return_value=_client(handler)):
        with pytest.raises(LastFmApiError) as exc_info:
            await LastFmConnect.request("artist.getInfo", {"artist": "x"})

    assert exc_info.value.code == 10
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_request_retries_transient_server_errors_then_succeeds():
    responses = iter([httpx.Response(503, text="boom"), httpx.Response(200, json={"ok": True})])

    with patch.object(LastFmConnect, "_client_instance", return_value=_client(lambda request: next(responses))):
        assert await LastFmConnect.request("artist.getInfo", {"artist": "x"}) == {"ok": True}


@pytest.mark.asyncio
async def test_request_gives_up_after_max_attempts_without_leaking_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout(f"timeout em {request.url}")

    with patch.object(LastFmConnect, "_client_instance", return_value=_client(handler)):
        with pytest.raises(LastFmUnavailableError) as exc_info:
            await LastFmConnect.request("artist.getInfo", {"artist": "x"})

    assert SECRET not in exc_info.value.reason
    assert "ConnectTimeout" in exc_info.value.reason


@pytest.mark.asyncio
async def test_request_without_api_key_fails_before_any_network_call():
    with patch.object(lastfm_connection, "LASTFM_API_KEY", ""), patch.object(
        LastFmConnect, "_client_instance"
    ) as mock_client:
        with pytest.raises(LastFmApiError) as exc_info:
            await LastFmConnect.request("artist.getInfo", {"artist": "x"})

    assert exc_info.value.code == 10
    mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_api_key_overrides_the_configured_one_and_works_without_env_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.url.params)
        return httpx.Response(200, json={"results": {}})

    with patch.object(lastfm_connection, "LASTFM_API_KEY", ""), patch.object(
        LastFmConnect, "_client_instance", return_value=_client(handler)
    ):
        await LastFmConnect.request("artist.search", {"artist": "a"}, api_key="chave-a-validar")

    assert seen["api_key"] == "chave-a-validar"
