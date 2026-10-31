from typing import Literal

from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import get_json, image_url, map_page
from mcp_servers.tmdb_mcp.data.model.media_model import Credit, Page, PersonSummary

MAX_CREDITS = 30
CreditRole = Literal["cast", "crew"]


def _summary(raw: dict) -> PersonSummary:
    return PersonSummary(
        id=raw["id"],
        name=raw.get("name") or "",
        known_for_department=raw.get("known_for_department"),
        known_for=[item.get("title") or item.get("name") or "" for item in raw.get("known_for", [])],
        profile_url=image_url(raw.get("profile_path")),
    )


def _credit(raw: dict, role: CreditRole) -> Credit:
    return Credit(
        media_type=raw["media_type"],
        id=raw["id"],
        title=raw.get("title") or raw.get("name") or "",
        date=raw.get("release_date") or raw.get("first_air_date") or None,
        role=(raw.get("character") if role == "cast" else raw.get("job")) or None,
        vote_average=raw.get("vote_average"),
        vote_count=raw.get("vote_count"),
    )


class PersonGateway:
    @staticmethod
    async def search(query: str, page: int, language: str) -> Page[PersonSummary]:
        params = {"query": query, "page": page, "language": language, "include_adult": "false"}
        return map_page(await get_json("/search/person", params), _summary)

    @staticmethod
    async def get_credits(person_id: int, role: CreditRole, job: str | None, language: str) -> list[Credit] | None:
        raw = await get_json(f"/person/{person_id}/combined_credits", {"language": language})
        if raw is None:
            return None
        entries = [entry for entry in raw.get(role, []) if entry.get("media_type") in ("movie", "tv")]
        if job:
            entries = [entry for entry in entries if (entry.get("job") or "").casefold() == job.casefold()]
        entries.sort(key=lambda entry: entry.get("popularity") or 0, reverse=True)

        credits: list[Credit] = []
        seen: set[tuple[str, int]] = set()
        for entry in entries:
            key = (entry["media_type"], entry["id"])
            if key in seen:
                continue
            seen.add(key)
            credits.append(_credit(entry, role))
            if len(credits) == MAX_CREDITS:
                break
        return credits
