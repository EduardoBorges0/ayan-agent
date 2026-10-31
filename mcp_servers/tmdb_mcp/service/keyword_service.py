from mcp_servers.tmdb_mcp.data.gateway.tmdb.keyword_gateway import KeywordGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import MediaKind
from mcp_servers.tmdb_mcp.service.tmdb_call import clean_query, tmdb_call


class KeywordService:
    @staticmethod
    async def search(query: str, page: int = 1) -> dict:
        query, error = clean_query(query)
        if error:
            return {"success": False, "error": error}
        return await tmdb_call(KeywordGateway.search(query, page))

    @staticmethod
    async def get_for_title(media_type: MediaKind, title_id: int) -> dict:
        return await tmdb_call(KeywordGateway.get_for_title(media_type, title_id))
