from mcp_servers.tmdb_mcp.data.gateway.tmdb.tv_gateway import TvGateway
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class TvService:
    @staticmethod
    async def search(query: str, page: int = 1) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(TvGateway.search(query, page, TMDB_LANGUAGE))

    @staticmethod
    async def get_details(tv_id: int) -> dict:
        return await tmdb_call(TvGateway.get_details(tv_id, TMDB_LANGUAGE))
