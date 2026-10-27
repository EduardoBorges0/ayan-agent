from unittest.mock import AsyncMock, patch

import pytest

from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError
from mcp_servers.lastfm_mcp.data.model.lastfm_model import AlbumInfo, ArtistCorrection, ArtistInfo
from mcp_servers.lastfm_mcp.service.album_service import AlbumService
from mcp_servers.lastfm_mcp.service.artist_service import ArtistService
from mcp_servers.lastfm_mcp.service.credentials_service import CredentialsService

GATEWAY = "mcp_servers.lastfm_mcp.service.artist_service.ArtistGateway"
ALBUM_GATEWAY = "mcp_servers.lastfm_mcp.service.album_service.AlbumGateway"
AUTH_GATEWAY = "mcp_servers.lastfm_mcp.service.credentials_service.AuthenticationGateway"
VALID_MBID = "a74b1b7f-71a5-4011-9441-d0b5e4122711"

@pytest.mark.asyncio
@patch(GATEWAY)
async def test_get_info_drops_full_bio_by_default(mock_gateway):
    mock_gateway.get_info = AsyncMock(return_value=ArtistInfo(name="Radiohead", summary="curto", content="longo"))

    result = await ArtistService.get_info(artist="Radiohead")

    assert result["success"] is True
    assert result["data"].summary == "curto"
    assert result["data"].content is None


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_get_info_keeps_full_bio_when_requested(mock_gateway):
    mock_gateway.get_info = AsyncMock(return_value=ArtistInfo(name="Radiohead", content="longo"))

    result = await ArtistService.get_info(artist="Radiohead", full_bio=True)

    assert result["data"].content == "longo"


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_returns_not_found_when_gateway_returns_none(mock_gateway):
    mock_gateway.get_info = AsyncMock(return_value=None)

    result = await ArtistService.get_info(artist="Inexistente")

    assert result == {"success": False, "error": "not_found"}


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_requires_artist_or_mbid(mock_gateway):
    mock_gateway.get_info = AsyncMock()

    result = await ArtistService.get_info()

    assert result["error"] == "invalid_input"
    mock_gateway.get_info.assert_not_called()


@pytest.mark.asyncio
@patch(GATEWAY)
@pytest.mark.parametrize(
    "kwargs",
    [
        {"mbid": "não-é-uuid"},
        {"artist": "x" * 201},
        {"artist": "Radiohead", "username": "nome inválido!"},
        {"artist": "Radiohead", "lang": "portugues"},
        {"artist": "Linha\nnova"},
    ],
)
async def test_rejects_invalid_input_before_calling_lastfm(mock_gateway, kwargs):
    mock_gateway.get_info = AsyncMock()

    result = await ArtistService.get_info(**kwargs)

    assert result["error"] == "invalid_input"
    mock_gateway.get_info.assert_not_called()


@pytest.mark.asyncio
@patch(GATEWAY)
@pytest.mark.parametrize("limit", [0, 51, -1, True, "10"])
async def test_rejects_limit_out_of_range(mock_gateway, limit):
    mock_gateway.get_similar = AsyncMock()

    result = await ArtistService.get_similar(artist="Radiohead", limit=limit)

    assert result["error"] == "invalid_input"
    mock_gateway.get_similar.assert_not_called()


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_mbid_alone_is_enough_and_is_lowercased(mock_gateway):
    mock_gateway.get_top_tags = AsyncMock(return_value=[])

    result = await ArtistService.get_top_tags(mbid=VALID_MBID.upper())

    assert result["success"] is True
    mock_gateway.get_top_tags.assert_awaited_once_with(None, VALID_MBID, True)


@pytest.mark.asyncio
@patch(GATEWAY)
@pytest.mark.parametrize(
    ("code", "expected"), [(10, "invalid_api_key"), (26, "invalid_api_key"), (29, "rate_limited"), (4, "lastfm_error")]
)
async def test_maps_lastfm_api_errors(mock_gateway, code, expected):
    mock_gateway.get_top_tags = AsyncMock(side_effect=LastFmApiError(code, "mensagem"))

    result = await ArtistService.get_top_tags(artist="Radiohead")

    assert result["success"] is False
    assert result["error"] == expected


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_maps_unavailable_error_with_reason(mock_gateway):
    mock_gateway.search = AsyncMock(side_effect=LastFmUnavailableError("falha de rede (ReadTimeout)"))

    result = await ArtistService.search("radio")

    assert result == {"success": False, "error": "unavailable", "detail": "falha de rede (ReadTimeout)"}


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_get_correction_without_correction_is_success_not_error(mock_gateway):
    mock_gateway.get_correction = AsyncMock(return_value=None)

    result = await ArtistService.get_correction("Radiohead")

    assert result["success"] is True
    assert result["data"] == ArtistCorrection(name="Radiohead", corrected=False)


@pytest.mark.asyncio
@patch(GATEWAY)
async def test_get_user_tags_requires_user(mock_gateway):
    mock_gateway.get_user_tags = AsyncMock()

    result = await ArtistService.get_user_tags(user="", artist="Radiohead")

    assert result["error"] == "invalid_input"
    mock_gateway.get_user_tags.assert_not_called()


@pytest.mark.asyncio
@patch(ALBUM_GATEWAY)
async def test_get_info_drops_full_wiki_by_default(mock_gateway):
    mock_gateway.get_info = AsyncMock(return_value=AlbumInfo(name="Kid A", summary="curto", content="longo"))

    result = await AlbumService.get_info(artist="Radiohead", album="Kid A")

    assert result["success"] is True
    assert result["data"].content is None


@pytest.mark.asyncio
@patch(ALBUM_GATEWAY)
@pytest.mark.parametrize("kwargs", [{}, {"artist": "Radiohead"}, {"album": "Kid A"}])
async def test_requires_artist_and_album_when_no_mbid(mock_gateway, kwargs):
    mock_gateway.get_info = AsyncMock()

    result = await AlbumService.get_info(**kwargs)

    assert result["error"] == "invalid_input"
    mock_gateway.get_info.assert_not_called()


@pytest.mark.asyncio
@patch(ALBUM_GATEWAY)
async def test_mbid_alone_is_enough(mock_gateway):
    mock_gateway.get_top_tags = AsyncMock(return_value=[])

    result = await AlbumService.get_top_tags(mbid=VALID_MBID)

    assert result["success"] is True


@pytest.mark.asyncio
@patch(ALBUM_GATEWAY)
async def test_returns_not_found_when_album_does_not_exist(mock_gateway):
    mock_gateway.get_info = AsyncMock(return_value=None)

    result = await AlbumService.get_info(artist="X", album="Y")

    assert result == {"success": False, "error": "not_found"}


@pytest.mark.asyncio
@patch(ALBUM_GATEWAY)
async def test_search_requires_text(mock_gateway):
    mock_gateway.search = AsyncMock()

    result = await AlbumService.search("   ")

    assert result["error"] == "invalid_input"


@pytest.mark.asyncio
async def test_empty_key_is_rejected_without_calling_lastfm():
    with patch(AUTH_GATEWAY) as mock_gateway:
        mock_gateway.is_key_valid = AsyncMock()

        result = await CredentialsService.validate_key("   ")

    assert result == {"success": False, "error": "empty_key"}
    mock_gateway.is_key_valid.assert_not_called()


@pytest.mark.asyncio
@patch(AUTH_GATEWAY)
async def test_valid_key_is_returned_trimmed(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(return_value=True)

    result = await CredentialsService.validate_key("  chave-boa \n")

    assert result == {"success": True, "data": "chave-boa"}
    mock_gateway.is_key_valid.assert_awaited_once_with("chave-boa")


@pytest.mark.asyncio
@patch(AUTH_GATEWAY)
async def test_rejected_key_is_reported_as_invalid(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(return_value=False)

    assert await CredentialsService.validate_key("chave-errada") == {"success": False, "error": "invalid_key"}


@pytest.mark.asyncio
@patch(AUTH_GATEWAY)
async def test_unreachable_lastfm_is_not_reported_as_invalid_key(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(side_effect=LastFmUnavailableError("falha de rede (ConnectError)"))

    result = await CredentialsService.validate_key("chave")

    assert result == {"success": False, "error": "lastfm_unavailable", "detail": "falha de rede (ConnectError)"}


@pytest.mark.asyncio
@patch(AUTH_GATEWAY)
async def test_unexpected_api_error_is_not_reported_as_invalid_key(mock_gateway):
    mock_gateway.is_key_valid = AsyncMock(side_effect=LastFmApiError(29, "Rate limit exceeded"))

    result = await CredentialsService.validate_key("chave")

    assert result["error"] == "lastfm_unavailable"
    assert "Rate limit" in result["detail"]
