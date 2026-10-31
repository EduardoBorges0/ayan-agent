from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.tmdb_mcp.data.gateway.tmdb.movie_gateway import MovieListCategory
from mcp_servers.tmdb_mcp.data.gateway.tmdb.person_gateway import CreditRole
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import MediaKind, Relation
from mcp_servers.tmdb_mcp.data.gateway.tmdb.trending_gateway import MediaType, TimeWindow
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tv_gateway import TvListCategory
from mcp_servers.tmdb_mcp.data.model.media_model import (
    CompanySummary,
    Credit,
    GenreSummary,
    KeywordSummary,
    MediaItem,
    MovieDetails,
    MovieSummary,
    Page,
    PersonSummary,
    TvShowDetails,
    TvShowSummary,
)
from mcp_servers.tmdb_mcp.service.company_service import CompanyService
from mcp_servers.tmdb_mcp.service.genre_service import GenreService
from mcp_servers.tmdb_mcp.service.keyword_service import KeywordService
from mcp_servers.tmdb_mcp.service.media_service import MediaService
from mcp_servers.tmdb_mcp.service.movie_service import MovieService
from mcp_servers.tmdb_mcp.service.person_service import PersonService
from mcp_servers.tmdb_mcp.service.tmdb_call import MAX_QUERY_LENGTH
from mcp_servers.tmdb_mcp.service.trending_service import TrendingService
from mcp_servers.tmdb_mcp.service.tv_service import TvService

mcp = MCPServer(
    name="tmdb",
    instructions=(
        "Ferramentas para consultar o TMDB (The Movie Database). "
        "Por género, nota, ano, duração, país, plataforma, etc.: obtém os IDs dos géneros com list_genres "
        "(os de filmes e de séries são diferentes) e usa discover_movies ou discover_tv_shows. "
        "«Parecido com X»: encontra o ID com search_movies/search_tv_shows e chama get_related_movies/"
        "get_related_tv_shows (similar = mesmo estilo, recommendations = quem gostou também viu), ou usa "
        "get_title_keywords e filtra por with_keywords. "
        "Os filtros por pessoa, empresa ou palavra-chave precisam de IDs: search_people, search_companies e "
        "search_keywords devolvem-nos."
    ),
)

_READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

_ERROR_MESSAGES = {
    "empty_query": "A pesquisa está vazia.",
    "query_too_long": f"A pesquisa tem mais de {MAX_QUERY_LENGTH} caracteres.",
    "not_found": "Não existe nenhum resultado com esse ID no TMDB.",
    "tmdb_auth_failed": "Chave do TMDB inválida ou em falta",
    "tmdb_unavailable": "Não foi possível contactar o TMDB",
}

_ID_LIST = r"^\d+([,|]\d+)*$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_AND_OR = "Vírgula = E, barra vertical = OU."

PageNumber = Annotated[int, Field(ge=1, le=500, description="Página de resultados, de 1 a 500.")]
Query = Annotated[str, Field(description="Texto a pesquisar.")]
MediaKindParam = Annotated[MediaKind, Field(description="movie (filmes) ou tv (séries).")]
RelationParam = Annotated[
    Relation,
    Field(description="recommendations (quem gostou também viu) ou similar (mesmo estilo e palavras-chave)."),
]

# Filtros partilhados pelo discover de filmes e de séries.
GenreIds = Annotated[str | None, Field(pattern=_ID_LIST, description=f"IDs de géneros (list_genres). {_AND_OR}")]
ExcludedGenreIds = Annotated[str | None, Field(pattern=_ID_LIST, description="IDs de géneros a excluir.")]
KeywordIds = Annotated[str | None, Field(pattern=_ID_LIST, description=f"IDs de palavras-chave. {_AND_OR}")]
ExcludedKeywordIds = Annotated[str | None, Field(pattern=_ID_LIST, description="IDs de palavras-chave a excluir.")]
PersonIds = Annotated[str | None, Field(pattern=_ID_LIST, description=f"IDs de pessoas (search_people). {_AND_OR}")]
CompanyIds = Annotated[str | None, Field(pattern=_ID_LIST, description=f"IDs de empresas (search_companies). {_AND_OR}")]
ExcludedCompanyIds = Annotated[str | None, Field(pattern=_ID_LIST, description="IDs de empresas a excluir.")]
Rating = Annotated[float | None, Field(ge=0, le=10, description="Nota média do TMDB, de 0 a 10.")]
VoteCount = Annotated[int | None, Field(ge=0, description="Número de votos.")]
Runtime = Annotated[int | None, Field(ge=0, le=1000, description="Duração em minutos.")]
DateFilter = Annotated[str | None, Field(pattern=_DATE, description="Data no formato AAAA-MM-DD.")]
YearFilter = Annotated[int | None, Field(ge=1870, le=2100, description="Ano.")]
CountryCode = Annotated[
    str | None, Field(pattern=r"^[A-Za-z]{2}$", description="Código de país ISO 3166-1, ex.: BR, US, PT.")
]
LanguageCode = Annotated[
    str | None, Field(pattern=r"^[A-Za-z]{2}$", description="Idioma original, código ISO 639-1, ex.: pt, en, ko.")
]

MovieSort = Literal[
    "popularity.desc", "popularity.asc", "vote_average.desc", "vote_average.asc", "vote_count.desc", "vote_count.asc",
    "revenue.desc", "revenue.asc", "primary_release_date.desc", "primary_release_date.asc",
    "title.asc", "title.desc", "original_title.asc", "original_title.desc",
]
TvSort = Literal[
    "popularity.desc", "popularity.asc", "vote_average.desc", "vote_average.asc", "vote_count.desc", "vote_count.asc",
    "first_air_date.desc", "first_air_date.asc", "name.asc", "name.desc", "original_name.asc", "original_name.desc",
]


def _unwrap(result: dict):
    if result["success"]:
        return result["data"]
    message = _ERROR_MESSAGES[result["error"]]
    if result.get("detail"):
        message += f": {result['detail']}"
    raise ToolError(message)


def _given(arguments: dict) -> dict:
    return {name: value for name, value in arguments.items() if value is not None}


# --------------------------------------------------------------------------- filmes


@mcp.tool(annotations=_READ_ONLY)
async def search_movies(
    query: Query,
    year: Annotated[int | None, Field(ge=1870, le=2100, description="Ano de estreia, para filtrar.")] = None,
    page: PageNumber = 1,
) -> Page[MovieSummary]:
    """Pesquisa filmes no TMDB pelo título."""
    return _unwrap(await MovieService.search(query, page, year))


@mcp.tool(annotations=_READ_ONLY)
async def discover_movies(
    sort_by: MovieSort = "popularity.desc",
    page: PageNumber = 1,
    with_genres: GenreIds = None,
    without_genres: ExcludedGenreIds = None,
    vote_average_gte: Rating = None,
    vote_average_lte: Rating = None,
    vote_count_gte: VoteCount = None,
    vote_count_lte: VoteCount = None,
    year: YearFilter = None,
    primary_release_year: YearFilter = None,
    primary_release_date_gte: DateFilter = None,
    primary_release_date_lte: DateFilter = None,
    release_date_gte: DateFilter = None,
    release_date_lte: DateFilter = None,
    with_runtime_gte: Runtime = None,
    with_runtime_lte: Runtime = None,
    with_original_language: LanguageCode = None,
    with_origin_country: CountryCode = None,
    with_cast: PersonIds = None,
    with_crew: PersonIds = None,
    with_people: PersonIds = None,
    with_companies: CompanyIds = None,
    without_companies: ExcludedCompanyIds = None,
    with_keywords: KeywordIds = None,
    without_keywords: ExcludedKeywordIds = None,
    with_release_type: Annotated[
        str | None,
        Field(
            pattern=r"^[1-6]([,|][1-6])*$",
            description="Tipo de estreia: 1 estreia, 2 cinema limitada, 3 cinema, 4 digital, 5 físico, 6 TV. "
            "Combina com region.",
        ),
    ] = None,
    region: CountryCode = None,
) -> Page[MovieSummary]:
    """Descobre filmes por filtros: géneros, nota, votos, datas, duração, idioma, país, pessoas, empresas, \
palavras-chave. Para «os melhores», usa sort_by=vote_average.desc com \
vote_count_gte (200 ou mais), senão aparecem filmes com poucos votos."""
    arguments = dict(locals())
    page = arguments.pop("page")
    return _unwrap(await MovieService.discover(_given(arguments), page))


@mcp.tool(annotations=_READ_ONLY)
async def list_movies(
    category: Annotated[
        MovieListCategory, Field(description="popular, top_rated (mais bem avaliados), now_playing ou upcoming.")
    ],
    page: PageNumber = 1,
    region: Annotated[CountryCode, Field(description="País, para now_playing e upcoming. Ex.: BR.")] = None,
) -> Page[MovieSummary]:
    """Listas prontas de filmes do TMDB: populares, mais bem avaliados, em cartaz e próximas estreias."""
    return _unwrap(await MovieService.get_by_category(category, page, region))


@mcp.tool(annotations=_READ_ONLY)
async def get_movie_details(movie_id: Annotated[int, Field(ge=1, description="ID do filme no TMDB.")]) -> MovieDetails:
    """Detalhes de um filme: sinopse, géneros, duração, realizadores, elenco principal e trailer."""
    return _unwrap(await MovieService.get_details(movie_id))


@mcp.tool(annotations=_READ_ONLY)
async def get_related_movies(
    movie_id: Annotated[int, Field(ge=1, description="ID do filme no TMDB.")],
    relation: RelationParam = "recommendations",
    page: PageNumber = 1,
) -> Page[MovieSummary]:
    """Filmes parecidos com um filme (ou recomendados a quem gostou dele)."""
    return _unwrap(await MovieService.get_related(movie_id, relation, page))


# --------------------------------------------------------------------------- séries


@mcp.tool(annotations=_READ_ONLY)
async def search_tv_shows(query: Query, page: PageNumber = 1) -> Page[TvShowSummary]:
    """Pesquisa séries de televisão no TMDB pelo nome."""
    return _unwrap(await TvService.search(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def discover_tv_shows(
    sort_by: TvSort = "popularity.desc",
    page: PageNumber = 1,
    with_genres: GenreIds = None,
    without_genres: ExcludedGenreIds = None,
    vote_average_gte: Rating = None,
    vote_average_lte: Rating = None,
    vote_count_gte: VoteCount = None,
    vote_count_lte: VoteCount = None,
    first_air_date_year: YearFilter = None,
    first_air_date_gte: DateFilter = None,
    first_air_date_lte: DateFilter = None,
    air_date_gte: DateFilter = None,
    air_date_lte: DateFilter = None,
    include_null_first_air_dates: Annotated[bool | None, Field(description="Incluir séries sem data de estreia.")] = None,
    screened_theatrically: Annotated[bool | None, Field(description="Só séries exibidas no cinema.")] = None,
    timezone: Annotated[
        str | None,
        Field(pattern=r"^[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+){0,2}$", description="Fuso para air_date, ex.: America/Sao_Paulo."),
    ] = None,
    with_runtime_gte: Runtime = None,
    with_runtime_lte: Runtime = None,
    with_original_language: LanguageCode = None,
    with_origin_country: CountryCode = None,
    with_companies: CompanyIds = None,
    without_companies: ExcludedCompanyIds = None,
    with_networks: Annotated[int | None, Field(ge=1, description="ID de um canal/rede (ex.: HBO).")] = None,
    with_keywords: KeywordIds = None,
    without_keywords: ExcludedKeywordIds = None,
    with_status: Annotated[
        str | None,
        Field(
            pattern=r"^[0-5]([,|][0-5])*$",
            description="0 em exibição, 1 planeada, 2 em produção, 3 terminada, 4 cancelada, 5 piloto. "
            f"{_AND_OR}",
        ),
    ] = None,
    with_type: Annotated[
        str | None,
        Field(
            pattern=r"^[0-6]([,|][0-6])*$",
            description="0 documentário, 1 notícias, 2 minissérie, 3 reality, 4 com argumento, 5 talk show, "
            f"6 vídeo. {_AND_OR}",
        ),
    ] = None,
) -> Page[TvShowSummary]:
    """Descobre séries por filtros: géneros, nota, votos, datas, duração, idioma, país, canal, estado, tipo, \
empresas e palavras-chave. Para «as melhores», usa sort_by=vote_average.desc com vote_count_gte \
(200 ou mais)."""
    arguments = dict(locals())
    page = arguments.pop("page")
    return _unwrap(await TvService.discover(_given(arguments), page))


@mcp.tool(annotations=_READ_ONLY)
async def list_tv_shows(
    category: Annotated[
        TvListCategory, Field(description="popular, top_rated (mais bem avaliadas), airing_today ou on_the_air.")
    ],
    page: PageNumber = 1,
    timezone: Annotated[
        str | None,
        Field(
            pattern=r"^[A-Za-z0-9_+\-]+(/[A-Za-z0-9_+\-]+){0,2}$",
            description="Fuso, para airing_today e on_the_air. Ex.: America/Sao_Paulo.",
        ),
    ] = None,
) -> Page[TvShowSummary]:
    """Listas prontas de séries do TMDB: populares, mais bem avaliadas, a passar hoje e em exibição."""
    return _unwrap(await TvService.get_by_category(category, page, timezone))


@mcp.tool(annotations=_READ_ONLY)
async def get_tv_show_details(tv_id: Annotated[int, Field(ge=1, description="ID da série no TMDB.")]) -> TvShowDetails:
    """Detalhes de uma série: sinopse, géneros, temporadas, criadores, canais, elenco e trailer."""
    return _unwrap(await TvService.get_details(tv_id))


@mcp.tool(annotations=_READ_ONLY)
async def get_related_tv_shows(
    tv_id: Annotated[int, Field(ge=1, description="ID da série no TMDB.")],
    relation: RelationParam = "recommendations",
    page: PageNumber = 1,
) -> Page[TvShowSummary]:
    """Séries parecidas com uma série (ou recomendadas a quem gostou dela)."""
    return _unwrap(await TvService.get_related(tv_id, relation, page))


# --------------------------------------------------------------------------- géneros e palavras-chave


@mcp.tool(annotations=_READ_ONLY)
async def list_genres(media_type: MediaKindParam) -> list[GenreSummary]:
    """Lista de géneros com os respetivos IDs, para usar em with_genres. Os de filmes e séries são diferentes."""
    return _unwrap(await GenreService.get_all(media_type))


@mcp.tool(annotations=_READ_ONLY)
async def search_keywords(query: Query, page: PageNumber = 1) -> Page[KeywordSummary]:
    """Pesquisa palavras-chave (temas, ex.: vingança, viagem no tempo) para usar em with_keywords."""
    return _unwrap(await KeywordService.search(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def get_title_keywords(
    media_type: MediaKindParam, title_id: Annotated[int, Field(ge=1, description="ID do filme ou da série.")]
) -> list[KeywordSummary]:
    """Palavras-chave de um filme ou série, úteis para encontrar títulos parecidos com with_keywords."""
    return _unwrap(await KeywordService.get_for_title(media_type, title_id))


# --------------------------------------------------------------------------- pessoas e empresas


@mcp.tool(annotations=_READ_ONLY)
async def search_people(query: Query, page: PageNumber = 1) -> Page[PersonSummary]:
    """Pesquisa atores, realizadores e outras pessoas do cinema e televisão."""
    return _unwrap(await PersonService.search(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def get_person_credits(
    person_id: Annotated[int, Field(ge=1, description="ID da pessoa no TMDB.")],
    role: Annotated[CreditRole, Field(description="cast (como ator) ou crew (equipa técnica).")] = "cast",
    job: Annotated[str | None, Field(max_length=60, description="Função na equipa, ex.: Director. Só com crew.")] = None,
) -> list[Credit]:
    """Filmes e séries em que uma pessoa trabalhou (até 30, os mais populares primeiro)."""
    return _unwrap(await PersonService.get_credits(person_id, role, job))


@mcp.tool(annotations=_READ_ONLY)
async def search_companies(query: Query, page: PageNumber = 1) -> Page[CompanySummary]:
    """Pesquisa estúdios e produtoras, para usar em with_companies."""
    return _unwrap(await CompanyService.search(query, page))


# --------------------------------------------------------------------------- pesquisa geral e tendências


@mcp.tool(annotations=_READ_ONLY)
async def search_multi(query: Query, page: PageNumber = 1) -> Page[MediaItem]:
    """Pesquisa filmes, séries e pessoas de uma só vez, quando não se sabe de que tipo é."""
    return _unwrap(await MediaService.search_multi(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def get_trending(
    media_type: Annotated[MediaType, Field(description="all, movie, tv ou person.")] = "all",
    time_window: Annotated[TimeWindow, Field(description="day (hoje) ou week (esta semana).")] = "week",
) -> list[MediaItem]:
    """Filmes, séries ou pessoas em tendência no TMDB."""
    return _unwrap(await TrendingService.get_trending(media_type, time_window))
