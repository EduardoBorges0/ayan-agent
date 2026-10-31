from mcp_servers.tmdb_mcp.data.gateway.tmdb.media_gateway import MediaGateway
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class MediaService:
    @staticmethod
    async def search_multi(query: str, page: int = 1) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(MediaGateway.search_multi(query, page, TMDB_LANGUAGE))
