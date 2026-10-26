from unittest.mock import AsyncMock, patch

import pytest

from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import TmdbAuthError, TmdbUnavailableError
from mcp_servers.tmdb_mcp.service.credentials_service import CredentialsService
from mcp_servers.tmdb_mcp.service.movie_service import MovieService
from mcp_servers.tmdb_mcp.service.tv_service import TvService


@pytest.mark.asyncio
@pytest.mark.parametrize("query, error", [("   ", "empty_query"), ("x" * 201, "query_too_long")])
@patch("mcp_servers.tmdb_mcp.service.movie_service.MovieGateway")
async def test_invalid_queries_are_rejected_without_calling_tmdb(mock_gateway, query, error):
    result = await MovieService.search(query)

    assert result == {"success": False, "error": error}
    mock_gateway.search.assert_not_called()


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.movie_service.MovieGateway")
async def test_search_normalizes_spaces_before_calling_tmdb(mock_gateway):
    mock_gateway.search = AsyncMock(return_value="página")

    result = await MovieService.search("  o   padrinho ", page=2, year=1972)

    assert result == {"success": True, "data": "página"}
    mock_gateway.search.assert_awaited_once_with("o padrinho", 2, 1972, "pt-PT")


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.tv_service.TvGateway")
async def test_unknown_id_returns_not_found(mock_gateway):
    mock_gateway.get_details = AsyncMock(return_value=None)

    assert await TvService.get_details(42) == {"success": False, "error": "not_found"}


@pytest.mark.asyncio
@pytest.mark.parametrize("exception, error", [
    (TmdbAuthError("Invalid API key."), "tmdb_auth_failed"),
    (TmdbUnavailableError("HTTP 503"), "tmdb_unavailable"),
])
@patch("mcp_servers.tmdb_mcp.service.movie_service.MovieGateway")
async def test_tmdb_failures_are_returned_with_reason(mock_gateway, exception, error):
    mock_gateway.get_details = AsyncMock(side_effect=exception)

    result = await MovieService.get_details(603)

    assert result == {"success": False, "error": error, "detail": exception.reason}


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.credentials_service.AuthenticationGateway")
async def test_rejected_key_is_reported_as_invalid(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(return_value=False)

    result = await CredentialsService.validate_key("chave-errada")

    assert result == {"success": False, "error": "invalid_key"}


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.credentials_service.AuthenticationGateway")
async def test_valid_key_is_returned_trimmed(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(return_value=True)

    result = await CredentialsService.validate_key("  chave-boa  ")

    assert result == {"success": True, "data": "chave-boa"}
    mock_gateway.is_key_valid.assert_awaited_once_with("chave-boa")


@pytest.mark.asyncio
@patch("mcp_servers.tmdb_mcp.service.credentials_service.AuthenticationGateway")
async def test_empty_key_is_rejected_without_calling_tmdb(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock()

    assert await CredentialsService.validate_key("   ") == {"success": False, "error": "empty_key"}
    mock_gateway.is_key_valid.assert_not_called()
