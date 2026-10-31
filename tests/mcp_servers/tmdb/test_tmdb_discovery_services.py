from unittest.mock import AsyncMock, patch

import pytest

from mcp_servers.tmdb_mcp.service.company_service import CompanyService
from mcp_servers.tmdb_mcp.service.genre_service import GenreService
from mcp_servers.tmdb_mcp.service.keyword_service import KeywordService
from mcp_servers.tmdb_mcp.service.media_service import MediaService
from mcp_servers.tmdb_mcp.service.movie_service import MovieService
from mcp_servers.tmdb_mcp.service.person_service import PersonService
from mcp_servers.tmdb_mcp.service.tv_service import TvService


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.movie_service.MovieGateway")
async def test_discover_movies_passes_filters_page_and_language(mock_gateway):
    mock_gateway.discover = AsyncMock(return_value="página")
    filters = {"with_genres": "28", "vote_average_gte": 6.1}

    result = await MovieService.discover(filters, page=2)

    assert result == {"success": True, "data": "página"}
    mock_gateway.discover.assert_awaited_once_with(filters, 2, "pt-PT")


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.tv_service.TvGateway")
async def test_tv_discover_and_lists_pass_arguments_to_the_gateway(mock_gateway):
    mock_gateway.discover = AsyncMock(return_value="a")
    mock_gateway.get_by_category = AsyncMock(return_value="b")

    await TvService.discover({"with_genres": "18"}, page=3)
    await TvService.get_by_category("on_the_air", 2, "America/Sao_Paulo")

    mock_gateway.discover.assert_awaited_once_with({"with_genres": "18"}, 3, "pt-PT")
    mock_gateway.get_by_category.assert_awaited_once_with("on_the_air", 2, "America/Sao_Paulo", "pt-PT")


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.movie_service.MovieGateway")
async def test_movie_lists_and_related_titles_pass_arguments_to_the_gateway(mock_gateway):
    mock_gateway.get_by_category = AsyncMock(return_value="lista")
    mock_gateway.get_related = AsyncMock(return_value=None)

    assert (await MovieService.get_by_category("upcoming", 1, "BR"))["data"] == "lista"
    related = await MovieService.get_related(18, "similar", 2)

    mock_gateway.get_by_category.assert_awaited_once_with("upcoming", 1, "BR", "pt-PT")
    mock_gateway.get_related.assert_awaited_once_with(18, "similar", 2, "pt-PT")
    assert related == {"success": False, "error": "not_found"}


@pytest.mark.asyncio
@pytest.mark.parametrize("service, method", [
    (MediaService, "search_multi"), (KeywordService, "search"),
    (CompanyService, "search"), (PersonService, "search"),
])
@pytest.mark.parametrize("query, error", [("   ", "empty_query"), ("x" * 201, "query_too_long")])
async def test_every_text_search_rejects_invalid_queries_without_calling_tmdb(service, method, query, error):
    assert await getattr(service, method)(query) == {"success": False, "error": error}


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.genre_service.GenreGateway")
async def test_genres_use_the_configured_language(mock_gateway):
    mock_gateway.get_all = AsyncMock(return_value=["género"])

    result = await GenreService.get_all("tv")

    assert result == {"success": True, "data": ["género"]}
    mock_gateway.get_all.assert_awaited_once_with("tv", "pt-PT")


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.keyword_service.KeywordGateway")
async def test_title_without_keywords_entry_is_not_found(mock_gateway):
    mock_gateway.get_for_title = AsyncMock(return_value=None)

    assert await KeywordService.get_for_title("movie", 1) == {"success": False, "error": "not_found"}


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.person_service.PersonGateway")
async def test_person_credits_normalize_the_job_filter(mock_gateway):
    mock_gateway.get_credits = AsyncMock(return_value=[])

    await PersonService.get_credits(1, "crew", "  Director ")
    await PersonService.get_credits(1)

    assert mock_gateway.get_credits.await_args_list[0].args == (1, "crew", "Director", "pt-PT")
    assert mock_gateway.get_credits.await_args_list[1].args == (1, "cast", None, "pt-PT")
