from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import Relation
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tv_gateway import TvGateway, TvListCategory
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
    async def discover(filters: dict, page: int = 1) -> dict:
        return await tmdb_call(TvGateway.discover(filters, page, TMDB_LANGUAGE))

    @staticmethod
    async def get_by_category(category: TvListCategory, page: int = 1, timezone: str | None = None) -> dict:
        return await tmdb_call(TvGateway.get_by_category(category, page, timezone, TMDB_LANGUAGE))

    @staticmethod
    async def get_details(tv_id: int) -> dict:
        return await tmdb_call(TvGateway.get_details(tv_id, TMDB_LANGUAGE))

    @staticmethod
    async def get_related(tv_id: int, relation: Relation = "recommendations", page: int = 1) -> dict:
        return await tmdb_call(TvGateway.get_related(tv_id, relation, page, TMDB_LANGUAGE))
