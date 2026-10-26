from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import (
    get_json,
    image_url,
    map_cast,
    map_page,
    map_trailer_url,
    video_languages,
)
from mcp_servers.tmdb_mcp.data.model.media_model import MovieDetails, MovieSummary, Page


def _summary(raw: dict) -> MovieSummary:
    return MovieSummary(
        id=raw["id"],
        title=raw.get("title") or raw.get("original_title") or "",
        original_title=raw.get("original_title"),
        release_date=raw.get("release_date") or None,
        overview=raw.get("overview") or None,
        vote_average=raw.get("vote_average"),
        poster_url=image_url(raw.get("poster_path")),
    )


class MovieGateway:
    @staticmethod
    async def search(query: str, page: int, year: int | None, language: str) -> Page[MovieSummary]:
        params = {"query": query, "page": page, "language": language, "include_adult": "false"}
        if year is not None:
            params["year"] = year
        return map_page(await get_json("/search/movie", params), _summary)

    @staticmethod
    async def get_details(movie_id: int, language: str) -> MovieDetails | None:
        raw = await get_json(
            f"/movie/{movie_id}",
            {
                "language": language,
                "append_to_response": "credits,videos",
                "include_video_language": video_languages(language),
            },
        )
        if raw is None:
            return None
        credits = raw.get("credits") or {}
        return MovieDetails(
            **_summary(raw).model_dump(),
            tagline=raw.get("tagline") or None,
            runtime_minutes=raw.get("runtime") or None,
            genres=[genre["name"] for genre in raw.get("genres", [])],
            status=raw.get("status"),
            directors=[member["name"] for member in credits.get("crew", []) if member.get("job") == "Director"],
            cast=map_cast(credits),
            trailer_url=map_trailer_url(raw.get("videos")),
            imdb_url=f"https://www.imdb.com/title/{raw['imdb_id']}/" if raw.get("imdb_id") else None,
            homepage=raw.get("homepage") or None,
        )

    @staticmethod
    async def get_recommendations(movie_id: int, page: int, language: str) -> Page[MovieSummary] | None:
        raw = await get_json(f"/movie/{movie_id}/recommendations", {"page": page, "language": language})
        return None if raw is None else map_page(raw, _summary)
