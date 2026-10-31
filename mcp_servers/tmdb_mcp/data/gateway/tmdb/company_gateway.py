from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json, map_page
from mcp_servers.tmdb_mcp.data.model.media_model import CompanySummary, Page


def _summary(raw: dict) -> CompanySummary:
    return CompanySummary(id=raw["id"], name=raw.get("name") or "", origin_country=raw.get("origin_country") or None)


class CompanyGateway:
    @staticmethod
    async def search(query: str, page: int) -> Page[CompanySummary]:
        return map_page(await get_json("/search/company", {"query": query, "page": page}), _summary)
