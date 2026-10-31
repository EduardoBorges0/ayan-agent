from mcp_servers.tmdb_mcp.data.gateway.tmdb.genre_gateway import GenreGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import MediaKind
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import tmdb_call


class GenreService:
    @staticmethod
    async def get_all(media_type: MediaKind) -> dict:
        return await tmdb_call(GenreGateway.get_all(media_type, TMDB_LANGUAGE))
