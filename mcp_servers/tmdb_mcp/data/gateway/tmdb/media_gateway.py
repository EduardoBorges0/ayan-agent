from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json, image_url, map_page
from mcp_servers.tmdb_mcp.data.model.media_model import MediaItem, Page


def to_media_item(raw: dict, default_media_type: str = "") -> MediaItem | None:
    media_type = raw.get("media_type") or default_media_type
    if media_type not in ("movie", "tv", "person"):
        return None
    return MediaItem(
        media_type=media_type,
        id=raw["id"],
        title=raw.get("title") or raw.get("name") or "",
        date=raw.get("release_date") or raw.get("first_air_date") or None,
        overview=raw.get("overview") or None,
        vote_average=raw.get("vote_average"),
        image_url=image_url(raw.get("poster_path") or raw.get("profile_path")),
        vote_count=raw.get("vote_count"),
    )


class MediaGateway:
    @staticmethod
    async def search_multi(query: str, page: int, language: str) -> Page[MediaItem]:
        params = {"query": query, "page": page, "language": language, "include_adult": "false"}
        return map_page(await get_json("/search/multi", params), to_media_item)
