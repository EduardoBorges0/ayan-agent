from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.tmdb_mcp.data.model.media_model import MovieSummary, Page
from mcp_servers.tmdb_mcp.server import mcp

EXPECTED_TOOLS = {
    "search_movies", "get_movie_details", "get_movie_recommendations",
    "search_tv_shows", "get_tv_show_details", "search_people", "get_trending",
}


@pytest.mark.asyncio
async def test_all_tools_are_registered_as_read_only():
    tools = await mcp.list_tools()

    assert {tool.name for tool in tools} == EXPECTED_TOOLS
    assert all(tool.annotations.read_only_hint for tool in tools)


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.MovieService")
async def test_search_movies_returns_structured_page(mock_service):
    page = Page[MovieSummary](page=1, total_pages=1, total_results=1, results=[MovieSummary(
        id=603, title="Matrix", original_title="The Matrix", release_date="1999-03-31",
        overview=None, vote_average=8.2, poster_url=None,
    )])
    mock_service.search = AsyncMock(return_value={"success": True, "data": page})

    result = await mcp.call_tool("search_movies", {"query": "matrix"})

    assert not result.is_error
    assert result.structured_content["results"][0]["title"] == "Matrix"
    mock_service.search.assert_awaited_once_with("matrix", 1, None)


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.MovieService")
async def test_service_error_becomes_tool_error_with_reason(mock_service):
    mock_service.get_details = AsyncMock(
        return_value={"success": False, "error": "tmdb_auth_failed", "detail": "Invalid API key."}
    )

    with pytest.raises(ToolError) as raised:
        await mcp.call_tool("get_movie_details", {"movie_id": 603})

    assert "Chave do TMDB inválida ou em falta: Invalid API key." in str(raised.value)


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.MovieService")
async def test_invalid_arguments_are_rejected_before_reaching_service(mock_service):
    mock_service.search = AsyncMock()

    with pytest.raises(ToolError):
        await mcp.call_tool("search_movies", {"query": "matrix", "page": 0})

    mock_service.search.assert_not_called()
