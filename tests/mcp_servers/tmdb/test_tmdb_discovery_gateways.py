import httpx
import pytest

from mcp_servers.tmdb_mcp.config.connections.tmdb_connection import TMDB_BASE_URL, TmdbConnect
from mcp_servers.tmdb_mcp.data.gateway.tmdb.company_gateway import CompanyGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.genre_gateway import GenreGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.keyword_gateway import KeywordGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.media_gateway import MediaGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.movie_gateway import MovieGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.person_gateway import MAX_CREDITS, PersonGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tv_gateway import TvGateway

requests: list[httpx.Request] = []


def _use_responses(monkeypatch, handler):
    requests.clear()

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = httpx.AsyncClient(base_url=TMDB_BASE_URL, transport=httpx.MockTransport(recording_handler))
    monkeypatch.setattr(TmdbConnect, "_client", client)


def _page(results):
    return {"page": 1, "total_pages": 1, "total_results": len(results), "results": results}


MOVIE = {
    "id": 18, "title": "Busca Implacável", "original_title": "Taken", "release_date": "2008-02-18",
    "overview": "Um ex-agente procura a filha.", "vote_average": 7.4, "vote_count": 12000, "poster_path": "/t.jpg",
}
SHOW = {"id": 1396, "name": "Breaking Bad", "first_air_date": "2008-01-20", "vote_average": 8.9, "vote_count": 14000}


# ---------------------------------------------------------------- discover


@pytest.mark.asyncio
async def test_discover_movies_translates_filters_to_tmdb_parameters(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([MOVIE])))

    page = await MovieGateway.discover(
        {
            "with_genres": "28", "without_genres": "27", "sort_by": "vote_average.desc",
            "vote_average_gte": 6.1, "vote_count_gte": 200, "with_runtime_lte": 120,
            "primary_release_date_gte": "2010-01-01",
        },
        page=2,
        language="pt-PT",
    )

    params = requests[0].url.params
    assert requests[0].url.path == "/3/discover/movie"
    assert params["with_genres"] == "28"
    assert params["without_genres"] == "27"
    assert params["sort_by"] == "vote_average.desc"
    assert params["vote_average.gte"] == "6.1"
    assert params["vote_count.gte"] == "200"
    assert params["with_runtime.lte"] == "120"
    assert params["primary_release_date.gte"] == "2010-01-01"
    assert params["page"] == "2"
    assert params["language"] == "pt-PT"
    assert "vote_average_gte" not in params
    assert page.results[0].title == "Busca Implacável"
    assert page.results[0].vote_count == 12000


@pytest.mark.asyncio
async def test_discover_never_lets_filters_override_fixed_parameters(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([])))

    await MovieGateway.discover({"include_adult": "true", "language": "en-US", "page": 99}, page=1, language="pt-PT")

    params = requests[0].url.params
    assert params["include_adult"] == "false"
    assert params["language"] == "pt-PT"
    assert params["page"] == "1"


@pytest.mark.asyncio
async def test_discover_tv_uses_tv_endpoint_and_maps_date_ranges_and_booleans(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([SHOW])))

    page = await TvGateway.discover(
        {"first_air_date_gte": "2020-01-01", "with_networks": 49, "include_null_first_air_dates": False, "with_status": "0"},
        page=1,
        language="pt-PT",
    )

    params = requests[0].url.params
    assert requests[0].url.path == "/3/discover/tv"
    assert params["first_air_date.gte"] == "2020-01-01"
    assert params["with_networks"] == "49"
    assert params["include_null_first_air_dates"] == "false"
    assert params["with_status"] == "0"
    assert page.results[0].vote_count == 14000


# ---------------------------------------------------------------- listas e relacionados


@pytest.mark.asyncio
async def test_movie_lists_use_category_path_and_uppercase_region(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([MOVIE])))

    await MovieGateway.get_by_category("now_playing", page=3, region="br", language="pt-PT")

    assert requests[0].url.path == "/3/movie/now_playing"
    assert requests[0].url.params["region"] == "BR"
    assert requests[0].url.params["page"] == "3"


@pytest.mark.asyncio
async def test_tv_lists_send_timezone_only_when_given(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([SHOW])))

    await TvGateway.get_by_category("airing_today", page=1, timezone="America/Sao_Paulo", language="pt-PT")
    await TvGateway.get_by_category("top_rated", page=1, timezone=None, language="pt-PT")

    assert requests[0].url.path == "/3/tv/airing_today"
    assert requests[0].url.params["timezone"] == "America/Sao_Paulo"
    assert requests[1].url.path == "/3/tv/top_rated"
    assert "timezone" not in requests[1].url.params


@pytest.mark.asyncio
@pytest.mark.parametrize("relation", ["similar", "recommendations"])
async def test_related_titles_use_the_requested_relation(monkeypatch, relation):
    _use_responses(monkeypatch, lambda request: httpx.Response(200, json=_page(
        [SHOW] if "/tv/" in request.url.path else [MOVIE]
    )))

    movies = await MovieGateway.get_related(18, relation, page=1, language="pt-PT")
    shows = await TvGateway.get_related(1396, relation, page=1, language="pt-PT")

    assert requests[0].url.path == f"/3/movie/18/{relation}"
    assert requests[1].url.path == f"/3/tv/1396/{relation}"
    assert movies.results[0].title == "Busca Implacável"
    assert shows.results[0].name == "Breaking Bad"


@pytest.mark.asyncio
async def test_related_titles_return_none_when_tmdb_says_not_found(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(404, json={"status_code": 34}))

    assert await MovieGateway.get_related(1, "similar", 1, "pt-PT") is None
    assert await TvGateway.get_related(1, "similar", 1, "pt-PT") is None


# ---------------------------------------------------------------- géneros e palavras-chave


@pytest.mark.asyncio
async def test_genres_are_listed_per_media_type(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={"genres": [{"id": 28, "name": "Ação"}]}))

    genres = await GenreGateway.get_all("movie", "pt-PT")

    assert requests[0].url.path == "/3/genre/movie/list"
    assert requests[0].url.params["language"] == "pt-PT"
    assert [(genre.id, genre.name) for genre in genres] == [(28, "Ação")]


@pytest.mark.asyncio
async def test_title_keywords_read_keywords_for_movies_and_results_for_tv(monkeypatch):
    def handler(request):
        if request.url.path == "/3/movie/18/keywords":
            return httpx.Response(200, json={"id": 18, "keywords": [{"id": 1, "name": "sequestro"}]})
        return httpx.Response(200, json={"id": 1396, "results": [{"id": 2, "name": "drogas"}]})

    _use_responses(monkeypatch, handler)

    movie_keywords = await KeywordGateway.get_for_title("movie", 18)
    tv_keywords = await KeywordGateway.get_for_title("tv", 1396)

    assert [keyword.name for keyword in movie_keywords] == ["sequestro"]
    assert [keyword.name for keyword in tv_keywords] == ["drogas"]


@pytest.mark.asyncio
async def test_keyword_search_and_missing_title(monkeypatch):
    _use_responses(monkeypatch, lambda request: (
        httpx.Response(404, json={}) if "keywords" in request.url.path
        else httpx.Response(200, json=_page([{"id": 9, "name": "vingança"}]))
    ))

    page = await KeywordGateway.search("vingança", 1)

    assert requests[0].url.path == "/3/search/keyword"
    assert requests[0].url.params["query"] == "vingança"
    assert page.results[0].id == 9
    assert await KeywordGateway.get_for_title("movie", 999999999) is None


# ---------------------------------------------------------------- empresas e pesquisa geral


@pytest.mark.asyncio
async def test_company_search_maps_name_and_country_and_sends_no_language(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([
        {"id": 5, "name": "Pixar", "origin_country": "US"},
    ])))

    companies = await CompanyGateway.search("pixar", 1)

    assert (companies.results[0].name, companies.results[0].origin_country) == ("Pixar", "US")
    assert requests[0].url.path == "/3/search/company"
    assert "language" not in requests[0].url.params


@pytest.mark.asyncio
async def test_multi_search_mixes_types_and_skips_unknown_ones(monkeypatch):
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json=_page([
        {"media_type": "movie", "id": 1, "title": "Filme", "vote_count": 10},
        {"media_type": "tv", "id": 2, "name": "Série"},
        {"media_type": "person", "id": 3, "name": "Atriz", "profile_path": "/a.jpg"},
        {"media_type": "collection", "id": 4, "name": "Coleção"},
    ])))

    page = await MediaGateway.search_multi("algo", 1, "pt-PT")

    assert requests[0].url.path == "/3/search/multi"
    assert requests[0].url.params["include_adult"] == "false"
    assert [(item.media_type, item.title) for item in page.results] == [
        ("movie", "Filme"), ("tv", "Série"), ("person", "Atriz"),
    ]
    assert page.results[0].vote_count == 10


# ---------------------------------------------------------------- créditos


def _cast(media_type, id, popularity, **extra):
    base = {"media_type": media_type, "id": id, "popularity": popularity, "vote_average": 7.0, "vote_count": 100}
    key = "title" if media_type == "movie" else "name"
    return {**base, key: f"T{id}", "character": f"Personagem {id}", **extra}


@pytest.mark.asyncio
async def test_person_credits_are_sorted_by_popularity_deduplicated_and_limited_to_movies_and_tv(monkeypatch):
    cast = [
        _cast("movie", 1, 10),
        _cast("tv", 2, 50),
        _cast("movie", 1, 10),
        {"media_type": "person", "id": 9, "popularity": 99, "name": "Alguém"},
    ]
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={"cast": cast, "crew": []}))

    credits = await PersonGateway.get_credits(3896, "cast", None, "pt-PT")

    assert requests[0].url.path == "/3/person/3896/combined_credits"
    assert [(credit.media_type, credit.id) for credit in credits] == [("tv", 2), ("movie", 1)]
    assert credits[0].role == "Personagem 2"


@pytest.mark.asyncio
async def test_person_crew_credits_can_be_filtered_by_job(monkeypatch):
    crew = [
        {**_cast("movie", 1, 5), "job": "Director"},
        {**_cast("movie", 2, 9), "job": "Producer"},
    ]
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={"cast": [], "crew": crew}))

    credits = await PersonGateway.get_credits(1, "crew", "director", "pt-PT")

    assert [(credit.id, credit.role) for credit in credits] == [(1, "Director")]


@pytest.mark.asyncio
async def test_person_credits_are_limited_and_missing_person_returns_none(monkeypatch):
    cast = [_cast("movie", i, i) for i in range(1, MAX_CREDITS + 15)]
    _use_responses(monkeypatch, lambda _: httpx.Response(200, json={"cast": cast, "crew": []}))
    assert len(await PersonGateway.get_credits(1, "cast", None, "pt-PT")) == MAX_CREDITS

    _use_responses(monkeypatch, lambda _: httpx.Response(404, json={}))
    assert await PersonGateway.get_credits(999999999, "cast", None, "pt-PT") is None
