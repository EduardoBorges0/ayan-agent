from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json, image_url, map_page
from mcp_servers.tmdb_mcp.data.model.media_model import Page, PersonSummary


def _summary(raw: dict) -> PersonSummary:
    return PersonSummary(
        id=raw["id"],
        name=raw.get("name") or "",
        known_for_department=raw.get("known_for_department"),
        known_for=[item.get("title") or item.get("name") or "" for item in raw.get("known_for", [])],
        profile_url=image_url(raw.get("profile_path")),
    )


class PersonGateway:
    @staticmethod
    async def search(query: str, page: int, language: str) -> Page[PersonSummary]:
        params = {"query": query, "page": page, "language": language, "include_adult": "false"}
        return map_page(await get_json("/search/person", params), _summary)
