from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import MediaKind, get_json, map_page
from mcp_servers.tmdb_mcp.data.model.media_model import KeywordSummary, Page


def _keyword(raw: dict) -> KeywordSummary:
    return KeywordSummary(id=raw["id"], name=raw.get("name") or "")


class KeywordGateway:
    @staticmethod
    async def search(query: str, page: int) -> Page[KeywordSummary]:
        return map_page(await get_json("/search/keyword", {"query": query, "page": page}), _keyword)

    @staticmethod
    async def get_for_title(media_type: MediaKind, title_id: int) -> list[KeywordSummary] | None:
        raw = await get_json(f"/{media_type}/{title_id}/keywords")
        if raw is None:
            return None
        # Os filmes devolvem "keywords"; as séries devolvem "results".
        entries = raw.get("keywords") if media_type == "movie" else raw.get("results")
        return [_keyword(entry) for entry in entries or []]
