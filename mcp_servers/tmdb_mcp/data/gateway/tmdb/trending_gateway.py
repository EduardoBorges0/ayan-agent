from typing import Literal

from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json, image_url
from mcp_servers.tmdb_mcp.data.model.media_model import TrendingItem

MediaType = Literal["all", "movie", "tv", "person"]
TimeWindow = Literal["day", "week"]


def _item(raw: dict, default_media_type: str) -> TrendingItem | None:
    media_type = raw.get("media_type") or default_media_type
    if media_type not in ("movie", "tv", "person"):
        return None
    return TrendingItem(
        media_type=media_type,
        id=raw["id"],
        title=raw.get("title") or raw.get("name") or "",
        date=raw.get("release_date") or raw.get("first_air_date") or None,
        overview=raw.get("overview") or None,
        vote_average=raw.get("vote_average"),
        image_url=image_url(raw.get("poster_path") or raw.get("profile_path")),
    )


class TrendingGateway:
    @staticmethod
    async def get(media_type: MediaType, time_window: TimeWindow, language: str) -> list[TrendingItem]:
        raw = await get_json(f"/trending/{media_type}/{time_window}", {"language": language})
        items = [_item(entry, media_type) for entry in (raw or {}).get("results", [])]
        return [item for item in items if item is not None]
