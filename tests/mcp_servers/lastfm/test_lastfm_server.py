import json
from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.lastfm_mcp.data.model.lastfm_model import ArtistInfo, ArtistRef, Page, Tag
from mcp_servers.lastfm_mcp.server import _unwrap, mcp

EXPECTED_TOOLS = {
    "artist_get_info", "artist_get_similar", "artist_get_top_albums", "artist_get_top_tracks",
    "artist_get_top_tags", "artist_get_user_tags", "artist_get_correction", "artist_search",
    "album_get_info", "album_get_top_tags", "album_get_user_tags", "album_search",
}


@pytest.mark.asyncio
async def test_only_read_only_artist_and_album_tools_are_registered():
    tools = await mcp.list_tools()

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert all(tool.annotations.read_only_hint for tool in tools)
    assert all(len(f"lastfm__{tool.name}") <= 64 for tool in tools)


@pytest.mark.asyncio
@patch("mcp_servers.lastfm_mcp.server.ArtistService")
async def test_artist_search_returns_compact_json_without_empty_fields(mock_service):
    page = Page(items=[ArtistRef(name="Radiohead", listeners=10)], page=1, total_pages=1, total=1)
    mock_service.search = AsyncMock(return_value={"success": True, "data": page})

    result = await mcp.call_tool("artist_search", {"artist": "radio"})

    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["items"] == [{"name": "Radiohead", "listeners": 10}]
    mock_service.search.assert_awaited_once_with("radio", 1, 10)


@pytest.mark.asyncio
@patch("mcp_servers.lastfm_mcp.server.ArtistService")
async def test_service_error_becomes_tool_error_with_reason(mock_service):
    mock_service.get_info = AsyncMock(
        return_value={"success": False, "error": "invalid_api_key", "detail": "Invalid API key"}
    )

    with pytest.raises(ToolError) as raised:
        await mcp.call_tool("artist_get_info", {"artist": "Radiohead"})

    assert "Chave do Last.fm inválida ou em falta" in str(raised.value)
    assert "Invalid API key" in str(raised.value)


@pytest.mark.asyncio
@patch("mcp_servers.lastfm_mcp.server.ArtistService")
@pytest.mark.parametrize("arguments", [{"artist": "Radiohead", "limit": 0}, {"artist": "Radiohead", "limit": 51}])
async def test_invalid_arguments_are_rejected_before_reaching_service(mock_service, arguments):
    mock_service.get_similar = AsyncMock()

    with pytest.raises(ToolError):
        await mcp.call_tool("artist_get_similar", arguments)

    mock_service.get_similar.assert_not_called()


def test_unwrap_serializes_dataclasses_and_drops_empty_fields():
    result = {"success": True, "data": ArtistInfo(name="Radiohead", listeners=10, tags=[Tag(name="rock")])}

    payload = json.loads(_unwrap(result))

    assert payload["name"] == "Radiohead"
    assert payload["tags"] == [{"name": "rock"}]
    assert "url" not in payload


@pytest.mark.parametrize(
    ("error", "fragment"),
    [("not_found", "não encontrou"), ("rate_limited", "limitou"), ("unavailable", "contactar")],
)
def test_unwrap_raises_tool_error_with_readable_message(error, fragment):
    with pytest.raises(ToolError) as raised:
        _unwrap({"success": False, "error": error})

    assert fragment in str(raised.value)
