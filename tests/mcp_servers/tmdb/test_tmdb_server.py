from unittest.mock import AsyncMock, patch

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_servers.tmdb_mcp.data.model.media_model import MovieSummary, Page
from mcp_servers.tmdb_mcp.server import mcp

EXPECTED_TOOLS = {
    "search_movies", "discover_movies", "list_movies", "get_movie_details", "get_related_movies",
    "search_tv_shows", "discover_tv_shows", "list_tv_shows", "get_tv_show_details", "get_related_tv_shows",
    "list_genres", "search_keywords", "get_title_keywords",
    "search_people", "get_person_credits", "search_companies",
    "search_multi", "get_trending",
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


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.MovieService")
async def test_discover_movies_sends_only_the_filters_that_were_given(mock_service):
    page = Page[MovieSummary](page=1, total_pages=1, total_results=0, results=[])
    mock_service.discover = AsyncMock(return_value={"success": True, "data": page})

    result = await mcp.call_tool("discover_movies", {
        "with_genres": "28", "vote_average_gte": 6.1, "vote_count_gte": 200,
        "sort_by": "vote_average.desc", "page": 2,
    })

    assert not result.is_error
    mock_service.discover.assert_awaited_once_with(
        {"sort_by": "vote_average.desc", "with_genres": "28", "vote_average_gte": 6.1, "vote_count_gte": 200}, 2,
    )


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.TvService")
async def test_discover_tv_shows_keeps_false_booleans(mock_service):
    page = Page[MovieSummary](page=1, total_pages=1, total_results=0, results=[])
    mock_service.discover = AsyncMock(return_value={"success": True, "data": page})

    await mcp.call_tool("discover_tv_shows", {"include_null_first_air_dates": False, "with_networks": 49})

    filters = mock_service.discover.await_args.args[0]
    assert filters["include_null_first_air_dates"] is False
    assert filters["with_networks"] == 49


@pytest.mark.asyncio
@pytest.mark.parametrize("tool, arguments", [
    ("discover_movies", {"with_genres": "28;DROP"}),
    ("discover_movies", {"with_genres": "28,"}),
    ("discover_movies", {"vote_average_gte": 11}),
    ("discover_movies", {"primary_release_date_gte": "2010"}),
    ("discover_movies", {"with_original_language": "port"}),
    ("discover_movies", {"with_release_type": "7"}),
    ("discover_movies", {"sort_by": "rating.desc"}),
    ("discover_tv_shows", {"with_status": "9"}),
    ("list_movies", {"category": "latest"}),
    ("list_tv_shows", {"category": "popular", "timezone": "../etc"}),
    ("list_genres", {"media_type": "person"}),
])
async def test_invalid_filter_values_are_rejected_before_reaching_a_service(tool, arguments):
    with pytest.raises(ToolError):
        await mcp.call_tool(tool, arguments)


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.server.MovieService")
async def test_related_movies_default_to_recommendations(mock_service):
    page = Page[MovieSummary](page=1, total_pages=1, total_results=0, results=[])
    mock_service.get_related = AsyncMock(return_value={"success": True, "data": page})

    await mcp.call_tool("get_related_movies", {"movie_id": 18})
    await mcp.call_tool("get_related_movies", {"movie_id": 18, "relation": "similar", "page": 2})

    assert mock_service.get_related.await_args_list[0].args == (18, "recommendations", 1)
    assert mock_service.get_related.await_args_list[1].args == (18, "similar", 2)
