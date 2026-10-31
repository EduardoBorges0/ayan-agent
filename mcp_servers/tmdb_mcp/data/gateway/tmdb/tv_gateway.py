from typing import Literal

from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import (
    Relation,
    discover_params,
    get_json,
    image_url,
    map_cast,
    map_page,
    map_trailer_url,
    video_languages,
)
from mcp_servers.tmdb_mcp.data.model.media_model import Page, TvShowDetails, TvShowSummary

TvListCategory = Literal["popular", "top_rated", "airing_today", "on_the_air"]


def _summary(raw: dict) -> TvShowSummary:
    return TvShowSummary(
        id=raw["id"],
        name=raw.get("name") or raw.get("original_name") or "",
        original_name=raw.get("original_name"),
        first_air_date=raw.get("first_air_date") or None,
        overview=raw.get("overview") or None,
        vote_average=raw.get("vote_average"),
        poster_url=image_url(raw.get("poster_path")),
        vote_count=raw.get("vote_count"),
    )


class TvGateway:
    @staticmethod
    async def search(query: str, page: int, language: str) -> Page[TvShowSummary]:
        params = {"query": query, "page": page, "language": language, "include_adult": "false"}
        return map_page(await get_json("/search/tv", params), _summary)

    @staticmethod
    async def discover(filters: dict, page: int, language: str) -> Page[TvShowSummary]:
        # Os parâmetros fixos vão por último para que os filtros nunca os possam substituir.
        params = {**discover_params(filters), "page": page, "language": language, "include_adult": "false"}
        return map_page(await get_json("/discover/tv", params), _summary)

    @staticmethod
    async def get_by_category(
        category: TvListCategory, page: int, timezone: str | None, language: str
    ) -> Page[TvShowSummary]:
        params = {"page": page, "language": language}
        if timezone:
            params["timezone"] = timezone
        return map_page(await get_json(f"/tv/{category}", params), _summary)

    @staticmethod
    async def get_details(tv_id: int, language: str) -> TvShowDetails | None:
        raw = await get_json(
            f"/tv/{tv_id}",
            {
                "language": language,
                "append_to_response": "credits,videos",
                "include_video_language": video_languages(language),
            },
        )
        if raw is None:
            return None
        return TvShowDetails(
            **_summary(raw).model_dump(),
            tagline=raw.get("tagline") or None,
            genres=[genre["name"] for genre in raw.get("genres", [])],
            status=raw.get("status"),
            last_air_date=raw.get("last_air_date") or None,
            number_of_seasons=raw.get("number_of_seasons"),
            number_of_episodes=raw.get("number_of_episodes"),
            creators=[creator["name"] for creator in raw.get("created_by", [])],
            networks=[network["name"] for network in raw.get("networks", [])],
            cast=map_cast(raw.get("credits")),
            trailer_url=map_trailer_url(raw.get("videos")),
        )

    @staticmethod
    async def get_related(tv_id: int, relation: Relation, page: int, language: str) -> Page[TvShowSummary] | None:
        raw = await get_json(f"/tv/{tv_id}/{relation}", {"page": page, "language": language})
        return None if raw is None else map_page(raw, _summary)
