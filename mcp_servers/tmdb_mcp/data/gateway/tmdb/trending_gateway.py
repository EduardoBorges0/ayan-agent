from typing import Literal

from mcp_servers.tmdb_mcp.data.gateway.tmdb.media_gateway import to_media_item
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json
from mcp_servers.tmdb_mcp.data.model.media_model import MediaItem

MediaType = Literal["all", "movie", "tv", "person"]
TimeWindow = Literal["day", "week"]


class TrendingGateway:
    @staticmethod
    async def get(media_type: MediaType, time_window: TimeWindow, language: str) -> list[MediaItem]:
        raw = await get_json(f"/trending/{media_type}/{time_window}", {"language": language})
        items = [to_media_item(entry, media_type) for entry in (raw or {}).get("results", [])]
        return [item for item in items if item is not None]
