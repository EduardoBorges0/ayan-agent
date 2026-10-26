from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_servers.tmdb_mcp.data.gateway.tmdb.trending_gateway import MediaType, TimeWindow
from mcp_servers.tmdb_mcp.data.model.media_model import (
    MovieDetails,
    MovieSummary,
    Page,
    PersonSummary,
    TrendingItem,
    TvShowDetails,
    TvShowSummary,
)
from mcp_servers.tmdb_mcp.service.movie_service import MovieService
from mcp_servers.tmdb_mcp.service.person_service import PersonService
from mcp_servers.tmdb_mcp.service.tmdb_call import MAX_QUERY_LENGTH
from mcp_servers.tmdb_mcp.service.trending_service import TrendingService
from mcp_servers.tmdb_mcp.service.tv_service import TvService

mcp = MCPServer(
    name="tmdb",
    instructions=(
        "Ferramentas para consultar o TMDB (The Movie Database): pesquisar filmes, séries e pessoas, "
        "ver detalhes, recomendações e tendências. Usa os IDs devolvidos pelas pesquisas para pedir detalhes."
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

PageNumber = Annotated[int, Field(ge=1, le=500, description="Página de resultados, de 1 a 500.")]
Query = Annotated[str, Field(description="Texto a pesquisar.")]


def _unwrap(result: dict):
    if result["success"]:
        return result["data"]
    message = _ERROR_MESSAGES[result["error"]]
    if result.get("detail"):
        message += f": {result['detail']}"
    raise ToolError(message)


@mcp.tool(annotations=_READ_ONLY)
async def search_movies(
    query: Query,
    year: Annotated[int | None, Field(ge=1870, le=2100, description="Ano de estreia, para filtrar.")] = None,
    page: PageNumber = 1,
) -> Page[MovieSummary]:
    """Pesquisa filmes no TMDB pelo título."""
    return _unwrap(await MovieService.search(query, page, year))


@mcp.tool(annotations=_READ_ONLY)
async def get_movie_details(movie_id: Annotated[int, Field(ge=1, description="ID do filme no TMDB.")]) -> MovieDetails:
    """Detalhes de um filme: sinopse, géneros, duração, realizadores, elenco principal e trailer."""
    return _unwrap(await MovieService.get_details(movie_id))


@mcp.tool(annotations=_READ_ONLY)
async def get_movie_recommendations(
    movie_id: Annotated[int, Field(ge=1, description="ID do filme no TMDB.")],
    page: PageNumber = 1,
) -> Page[MovieSummary]:
    """Filmes recomendados pelo TMDB para quem gostou de um filme."""
    return _unwrap(await MovieService.get_recommendations(movie_id, page))


@mcp.tool(annotations=_READ_ONLY)
async def search_tv_shows(query: Query, page: PageNumber = 1) -> Page[TvShowSummary]:
    """Pesquisa séries de televisão no TMDB pelo nome."""
    return _unwrap(await TvService.search(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def get_tv_show_details(tv_id: Annotated[int, Field(ge=1, description="ID da série no TMDB.")]) -> TvShowDetails:
    """Detalhes de uma série: sinopse, géneros, temporadas, criadores, canais, elenco e trailer."""
    return _unwrap(await TvService.get_details(tv_id))


@mcp.tool(annotations=_READ_ONLY)
async def search_people(query: Query, page: PageNumber = 1) -> Page[PersonSummary]:
    """Pesquisa atores, realizadores e outras pessoas do cinema e televisão."""
    return _unwrap(await PersonService.search(query, page))


@mcp.tool(annotations=_READ_ONLY)
async def get_trending(
    media_type: Annotated[MediaType, Field(description="all, movie, tv ou person.")] = "all",
    time_window: Annotated[TimeWindow, Field(description="day (hoje) ou week (esta semana).")] = "week",
) -> list[TrendingItem]:
    """Filmes, séries ou pessoas em tendência no TMDB."""
    return _unwrap(await TrendingService.get_trending(media_type, time_window))
