from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import MediaKind, get_json
from mcp_servers.tmdb_mcp.data.model.media_model import GenreSummary


class GenreGateway:
    @staticmethod
    async def get_all(media_type: MediaKind, language: str) -> list[GenreSummary]:
        raw = await get_json(f"/genre/{media_type}/list", {"language": language})
        return [GenreSummary(id=genre["id"], name=genre["name"]) for genre in (raw or {}).get("genres", [])]
