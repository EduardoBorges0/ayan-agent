from mcp_servers.tmdb_mcp.data.gateway.tmdb.movie_gateway import MovieGateway
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class MovieService:
    @staticmethod
    async def search(query: str, page: int = 1, year: int | None = None) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(MovieGateway.search(query, page, year, TMDB_LANGUAGE))

    @staticmethod
    async def get_details(movie_id: int) -> dict:
        return await tmdb_call(MovieGateway.get_details(movie_id, TMDB_LANGUAGE))

    @staticmethod
    async def get_recommendations(movie_id: int, page: int = 1) -> dict:
        return await tmdb_call(MovieGateway.get_recommendations(movie_id, page, TMDB_LANGUAGE))
