from mcp_servers.tmdb_mcp.data.gateway.tmdb.trending_gateway import MediaType, TimeWindow, TrendingGateway
from mcp_servers.tmdb_mcp.load_env import TMDB_LANGUAGE
from mcp_servers.tmdb_mcp.service.tmdb_call import tmdb_call


class TrendingService:
    @staticmethod
    async def get_trending(media_type: MediaType = "all", time_window: TimeWindow = "week") -> dict:
        return await tmdb_call(TrendingGateway.get(media_type, time_window, TMDB_LANGUAGE))
