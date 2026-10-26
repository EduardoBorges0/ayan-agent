import httpx
import pytest

from mcp_servers.tmdb_mcp.config.connections.tmdb_connection import TMDB_BASE_URL, TmdbConnect
from mcp_servers.tmdb_mcp.config.credentials import MissingTokenError
from mcp_servers.tmdb_mcp.data.gateway.tmdb.movie_gateway import MovieGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import TmdbAuthError, TmdbUnavailableError
from mcp_servers.tmdb_mcp.data.gateway.tmdb.trending_gateway import TrendingGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tv_gateway import TvGateway

requests: list[httpx.Request] = []


def _use_responses(monkeypatch, handler):
    requests.clear()

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = httpx.AsyncClient(base_url=TMDB_BASE_URL, transport=httpx.MockTransport(recording_handler))
    monkeypatch.setattr(TmdbConnect, "_client", client)


MOVIE = {
    "id": 603,
    "title": "Matrix",
    "original_title": "The Matrix",
    "release_date": "1999-03-31",
    "overview": "Um hacker descobre a verdade.",
    "vote_average": 8.2,
    "poster_path": "/matrix.jpg",
}


@pytest.mark.asyncio
async def test_search_movies_sends_query_and_maps_results(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={
        "page": 1, "total_pages": 1, "total_results": 2,
        "results": [MOVIE, {**MOVIE, "id": 1, "release_date": "", "poster_path": None, "overview": ""}],
    }))

    page = await MovieGateway.search("The Matrix", page=1, year=1999, language="pt-PT")

    request = requests[0]
    assert request.url.path == "/3/search/movie"
    assert request.url.params["query"] == "The Matrix"
    assert request.url.params["year"] == "1999"
    assert request.url.params["language"] == "pt-PT"
    assert page.results[0].poster_url == "https://image.tmdb.org/t/p/w500/matrix.jpg"
    assert page.results[1].release_date is None
    assert page.results[1].overview is None
    assert page.results[1].poster_url is None


@pytest.mark.asyncio
async def test_movie_details_maps_directors_cast_order_trailer_and_imdb(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={
        **MOVIE,
        "runtime": 136,
        "genres": [{"id": 1, "name": "Ação"}],
        "imdb_id": "tt0133093",
        "credits": {
            "cast": [
                {"name": "Carrie-Anne Moss", "character": "Trinity", "order": 2},
                {"name": "Keanu Reeves", "character": "Neo", "order": 0},
            ],
            "crew": [
                {"name": "Lana Wachowski", "job": "Director"},
                {"name": "Bill Pope", "job": "Director of Photography"},
            ],
        },
        "videos": {"results": [
            {"site": "Vimeo", "type": "Trailer", "key": "x"},
            {"site": "YouTube", "type": "Trailer", "key": "abc123"},
        ]},
    }))

    details = await MovieGateway.get_details(603, "pt-PT")

    assert requests[0].url.params["append_to_response"] == "credits,videos"
    assert requests[0].url.params["include_video_language"] == "pt,en,null"
    assert details.directors == ["Lana Wachowski"]
    assert [member.name for member in details.cast] == ["Keanu Reeves", "Carrie-Anne Moss"]
    assert details.trailer_url == "https://www.youtube.com/watch?v=abc123"
    assert details.imdb_url == "https://www.imdb.com/title/tt0133093/"
    assert details.runtime_minutes == 136
    assert details.genres == ["Ação"]


@pytest.mark.asyncio
async def test_details_return_none_when_tmdb_says_not_found(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(404, json={"status_code": 34}))

    assert await MovieGateway.get_details(999999999, "pt-PT") is None
    assert await TvGateway.get_details(999999999, "pt-PT") is None


@pytest.mark.asyncio
async def test_rejected_token_raises_auth_error_with_tmdb_message(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(401, json={"status_message": "Invalid API key."}))

    with pytest.raises(TmdbAuthError) as raised:
        await MovieGateway.search("x", 1, None, "pt-PT")

    assert raised.value.reason == "Invalid API key."


@pytest.mark.asyncio
async def test_server_error_raises_unavailable_with_status(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(503, json={"status_message": "Em manutenção."}))

    with pytest.raises(TmdbUnavailableError) as raised:
        await MovieGateway.search("x", 1, None, "pt-PT")

    assert raised.value.reason == "HTTP 503: Em manutenção."


@pytest.mark.asyncio
async def test_network_failure_raises_unavailable(monkeypatch):
    def fail(request):
        raise httpx.ConnectError("sem rede", request=request)

    _use_responses(monkeypatch, fail)

    with pytest.raises(TmdbUnavailableError):
        await MovieGateway.search("x", 1, None, "pt-PT")


@pytest.mark.asyncio
async def test_missing_token_raises_auth_error(monkeypatch):
    monkeypatch.setattr(TmdbConnect, "_client", None)

    def no_token():
        raise MissingTokenError("A chave do TMDB não está configurada.")

    monkeypatch.setattr("mcp_servers.tmdb_mcp.config.connections.tmdb_connection.get_api_key", no_token)

    with pytest.raises(TmdbAuthError) as raised:
        await MovieGateway.search("x", 1, None, "pt-PT")

    assert "não está configurada" in raised.value.reason


def test_v3_api_key_goes_in_query_and_v4_token_goes_in_header():
    v3 = TmdbConnect.new_client("0123456789abcdef0123456789abcdef")
    v4 = TmdbConnect.new_client("eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ4In0.assinatura")

    assert v3.params["api_key"] == "0123456789abcdef0123456789abcdef"
    assert "Authorization" not in v3.headers
    assert v4.headers["Authorization"] == "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJ4In0.assinatura"
    assert "api_key" not in v4.params


@pytest.mark.asyncio
async def test_tv_details_maps_seasons_creators_and_networks(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={
        "id": 1396, "name": "Breaking Bad", "original_name": "Breaking Bad", "first_air_date": "2008-01-20",
        "overview": "Um professor de química...", "vote_average": 8.9, "poster_path": "/bb.jpg",
        "number_of_seasons": 5, "number_of_episodes": 62,
        "created_by": [{"name": "Vince Gilligan"}], "networks": [{"name": "AMC"}],
        "genres": [{"name": "Drama"}], "credits": {"cast": []}, "videos": {"results": []},
    }))

    details = await TvGateway.get_details(1396, "pt-PT")

    assert details.number_of_seasons == 5
    assert details.creators == ["Vince Gilligan"]
    assert details.networks == ["AMC"]
    assert details.trailer_url is None


@pytest.mark.asyncio
async def test_trending_maps_mixed_media_and_skips_unknown_types(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={"results": [
        {"media_type": "movie", "id": 1, "title": "Filme", "release_date": "2026-10-01", "poster_path": "/f.jpg"},
        {"media_type": "tv", "id": 2, "name": "Série", "first_air_date": "2026-09-01"},
        {"media_type": "person", "id": 3, "name": "Atriz", "profile_path": "/a.jpg"},
        {"media_type": "collection", "id": 4, "name": "Coleção"},
    ]}))

    items = await TrendingGateway.get("all", "week", "pt-PT")

    assert requests[0].url.path == "/3/trending/all/week"
    assert [(item.media_type, item.title) for item in items] == [
        ("movie", "Filme"), ("tv", "Série"), ("person", "Atriz"),
    ]
    assert items[2].image_url == "https://image.tmdb.org/t/p/w500/a.jpg"
