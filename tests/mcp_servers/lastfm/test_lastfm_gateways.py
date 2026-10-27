from unittest.mock import AsyncMock, patch

import pytest

from mcp_servers.lastfm_mcp.data.gateway.album_gateway import AlbumGateway
from mcp_servers.lastfm_mcp.data.gateway.artist_gateway import ArtistGateway
from mcp_servers.lastfm_mcp.data.gateway.authentication_gateway import AuthenticationGateway
from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError

ARTIST_CONNECT = "mcp_servers.lastfm_mcp.data.gateway.artist_gateway.LastFmConnect"
ALBUM_CONNECT = "mcp_servers.lastfm_mcp.data.gateway.album_gateway.LastFmConnect"
AUTH_CONNECT = "mcp_servers.lastfm_mcp.data.gateway.authentication_gateway.LastFmConnect"

@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_get_info_maps_numbers_html_and_single_item_lists(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "artist": {
                "name": "Radiohead",
                "mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711",
                "url": "https://www.last.fm/music/Radiohead",
                "ontour": "0",
                "stats": {"listeners": "6000000", "playcount": "900000000"},
                "tags": {"tag": {"name": "alternative", "url": "https://x/alternative"}},
                "similar": {"artist": [{"name": "Thom Yorke", "url": "https://x/thom"}]},
                "bio": {
                    "summary": 'Banda inglesa &amp; famosa. <a href="https://x">Read more on Last.fm</a>',
                    "content": "<p>Texto longo</p>",
                },
            }
        }
    )

    info = await ArtistGateway.get_info("Radiohead", None, "pt", None, True)

    assert info.listeners == 6_000_000
    assert info.playcount == 900_000_000
    assert info.on_tour is False
    assert [tag.name for tag in info.tags] == ["alternative"]
    assert info.similar[0].name == "Thom Yorke"
    assert info.summary == "Banda inglesa & famosa."
    assert info.content == "Texto longo"
    params = mock_connect.request.call_args.args[1]
    assert params == {"artist": "Radiohead", "autocorrect": 1, "lang": "pt"}


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_mbid_takes_precedence_over_artist_name(mock_connect):
    mock_connect.request = AsyncMock(return_value=None)

    await ArtistGateway.get_top_tags("Qualquer", "a74b1b7f-71a5-4011-9441-d0b5e4122711", False)

    assert mock_connect.request.call_args.args[1] == {"mbid": "a74b1b7f-71a5-4011-9441-d0b5e4122711"}


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_get_info_returns_none_when_artist_does_not_exist(mock_connect):
    mock_connect.request = AsyncMock(return_value=None)

    assert await ArtistGateway.get_info("Inexistente", None, None, None, True) is None


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_get_top_albums_maps_page_and_nested_artist(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "topalbums": {
                "album": [{"name": "OK Computer", "playcount": "123", "artist": {"name": "Radiohead"}}],
                "@attr": {"page": "2", "totalPages": "9", "total": "85"},
            }
        }
    )

    result = await ArtistGateway.get_top_albums("Radiohead", None, 2, 10, True)

    assert (result.page, result.total_pages, result.total) == (2, 9, 85)
    assert result.items[0].artist == "Radiohead"
    assert result.items[0].playcount == 123


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_get_correction_returns_none_when_lastfm_has_no_correction(mock_connect):
    mock_connect.request = AsyncMock(return_value={"corrections": "\n"})

    assert await ArtistGateway.get_correction("Radiohed") is None


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_get_correction_maps_corrected_name(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "corrections": {
                "correction": {"artist": {"name": "Radiohead", "mbid": ""}, "@attr": {"artistcorrected": "1"}}
            }
        }
    )

    correction = await ArtistGateway.get_correction("Radiohed")

    assert correction.name == "Radiohead"
    assert correction.corrected is True
    assert correction.mbid is None


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_search_computes_page_from_opensearch_fields(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "results": {
                "opensearch:totalResults": "95",
                "opensearch:startIndex": "20",
                "opensearch:itemsPerPage": "10",
                "artistmatches": {"artist": [{"name": "Radiohead", "listeners": "6000000"}]},
            }
        }
    )

    result = await ArtistGateway.search("radio", 3, 10)

    assert (result.page, result.total_pages, result.total) == (3, 10, 95)
    assert result.items[0].listeners == 6_000_000


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_search_with_no_matches_returns_empty_page(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={"results": {"opensearch:totalResults": "0", "artistmatches": "\n"}}
    )

    result = await ArtistGateway.search("zzzz", 1, 10)

    assert result.items == []
    assert result.total == 0


@pytest.mark.asyncio
@patch(ARTIST_CONNECT)
async def test_user_input_is_sent_as_parameter_never_interpolated(mock_connect):
    mock_connect.request = AsyncMock(return_value=None)
    hostile = "AC/DC&api_key=roubada&method=user.getInfo"

    await ArtistGateway.get_info(hostile, None, None, None, False)

    assert mock_connect.request.call_args.args[1]["artist"] == hostile


@pytest.mark.asyncio
@patch(ALBUM_CONNECT)
async def test_get_info_handles_single_track_returned_as_object(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "album": {
                "name": "Kid A",
                "artist": "Radiohead",
                "listeners": "3000000",
                "playcount": "90000000",
                "tracks": {
                    "track": {"name": "Everything In Its Right Place", "duration": "251", "@attr": {"rank": "1"},
                              "artist": {"name": "Radiohead"}}
                },
                "tags": "",
                "wiki": {"published": "01 Jan 2000, 00:00", "summary": "Resumo <a href=\"x\">Read more on Last.fm</a>"},
            }
        }
    )

    info = await AlbumGateway.get_info("Radiohead", "Kid A", None, None, None, True)

    assert info.artist == "Radiohead"
    assert info.playcount == 90_000_000
    assert info.tags == []
    assert info.tracks[0].rank == 1
    assert info.tracks[0].duration_seconds == 251
    assert info.summary == "Resumo"
    assert mock_connect.request.call_args.args[1] == {"artist": "Radiohead", "album": "Kid A", "autocorrect": 1}


@pytest.mark.asyncio
@patch(ALBUM_CONNECT)
async def test_get_info_returns_none_when_album_does_not_exist(mock_connect):
    mock_connect.request = AsyncMock(return_value=None)

    assert await AlbumGateway.get_info("X", "Y", None, None, None, True) is None


@pytest.mark.asyncio
@patch(ALBUM_CONNECT)
async def test_get_user_tags_sends_user_parameter(mock_connect):
    mock_connect.request = AsyncMock(return_value={"tags": {"tag": [{"name": "favorito"}]}})

    tags = await AlbumGateway.get_user_tags("Radiohead", "Kid A", None, "rj", False)

    assert [tag.name for tag in tags] == ["favorito"]
    assert mock_connect.request.call_args.args[1]["user"] == "rj"


@pytest.mark.asyncio
@patch(ALBUM_CONNECT)
async def test_search_maps_album_matches(mock_connect):
    mock_connect.request = AsyncMock(
        return_value={
            "results": {
                "opensearch:totalResults": "1",
                "opensearch:startIndex": "0",
                "opensearch:itemsPerPage": "10",
                "albummatches": {"album": [{"name": "Kid A", "artist": "Radiohead", "mbid": ""}]},
            }
        }
    )

    result = await AlbumGateway.search("kid a", 1, 10)

    assert result.items[0].artist == "Radiohead"
    assert result.items[0].mbid is None


@pytest.mark.asyncio
@patch(AUTH_CONNECT)
async def test_key_is_valid_when_lastfm_answers_the_probe_request(mock_connect):
    mock_connect.request = AsyncMock(return_value={"results": {}})
    mock_connect.close = AsyncMock()

    assert await AuthenticationGateway.is_key_valid("chave-boa") is True
    assert mock_connect.request.call_args.kwargs == {"api_key": "chave-boa"}
    mock_connect.close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [10, 26])
@patch(AUTH_CONNECT)
async def test_key_is_rejected_when_lastfm_says_it_is_invalid_or_suspended(mock_connect, code):
    mock_connect.request = AsyncMock(side_effect=LastFmApiError(code, "Invalid API key"))
    mock_connect.close = AsyncMock()

    assert await AuthenticationGateway.is_key_valid("chave-errada") is False
    mock_connect.close.assert_awaited_once()


@pytest.mark.asyncio
@patch(AUTH_CONNECT)
async def test_other_api_errors_are_not_reported_as_an_invalid_key(mock_connect):
    mock_connect.request = AsyncMock(side_effect=LastFmApiError(29, "Rate limit exceeded"))
    mock_connect.close = AsyncMock()

    with pytest.raises(LastFmApiError):
        await AuthenticationGateway.is_key_valid("chave")


@pytest.mark.asyncio
@patch(AUTH_CONNECT)
async def test_unavailable_lastfm_is_propagated_to_the_service(mock_connect):
    mock_connect.request = AsyncMock(side_effect=LastFmUnavailableError("falha de rede (ConnectError)"))
    mock_connect.close = AsyncMock()

    with pytest.raises(LastFmUnavailableError):
        await AuthenticationGateway.is_key_valid("chave")
