import logging
import re
from typing import Literal

import httpx

from mcp_servers.tmdb_mcp.config.connections.tmdb_connection import TmdbConnect
from mcp_servers.tmdb_mcp.config.credentials import MissingTokenError
from mcp_servers.tmdb_mcp.data.model.media_model import CastMember, Page

logger = logging.getLogger(__name__)

IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
MAX_CAST = 10
_RANGE_SUFFIX = re.compile(r"_(gte|lte)$")

MediaKind = Literal["movie", "tv"]
Relation = Literal["similar", "recommendations"]


class TmdbAuthError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class TmdbUnavailableError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _status_message(response: httpx.Response) -> str:
    try:
        message = response.json().get("status_message")
    except ValueError:
        message = None
    return message or response.text[:200] or response.reason_phrase


async def get_json(path: str, params: dict | None = None) -> dict | None:
    try:
        client = TmdbConnect.get_client()
    except MissingTokenError as exc:
        raise TmdbAuthError(str(exc)) from exc
    try:
        response = await client.get(path, params=params)
    except httpx.HTTPError as exc:
        reason = f"{type(exc).__name__}: {exc}"
        logger.warning("Falha ao contactar o TMDB: %s", reason)
        raise TmdbUnavailableError(reason) from exc

    if response.status_code == 404:
        return None
    if response.status_code == 401:
        raise TmdbAuthError(_status_message(response))
    if response.is_error:
        reason = f"HTTP {response.status_code}: {_status_message(response)}"
        logger.warning("Erro do TMDB: %s", reason)
        raise TmdbUnavailableError(reason)
    return response.json()


def image_url(path: str | None) -> str | None:
    return f"{IMAGE_BASE_URL}{path}" if path else None


def video_languages(language: str) -> str:
    return f"{language.split('-')[0]},en,null"


def discover_params(filters: dict) -> dict:
    # Os filtros usam "_gte"/"_lte" nos nomes; a API do TMDB usa ".gte"/".lte".
    return {_RANGE_SUFFIX.sub(r".\1", name): value for name, value in filters.items() if value is not None}


def map_page(raw: dict | None, map_item) -> Page:
    if raw is None:
        return Page(page=1, total_pages=0, total_results=0, results=[])
    items = (map_item(item) for item in raw.get("results", []))
    return Page(
        page=raw["page"],
        total_pages=raw["total_pages"],
        total_results=raw["total_results"],
        results=[item for item in items if item is not None],
    )


def map_cast(credits: dict | None) -> list[CastMember]:
    cast = sorted((credits or {}).get("cast", []), key=lambda member: member.get("order", 999))
    return [CastMember(name=member["name"], character=member.get("character") or None) for member in cast[:MAX_CAST]]


def map_trailer_url(videos: dict | None) -> str | None:
    for video in (videos or {}).get("results", []):
        if video.get("site") == "YouTube" and video.get("type") == "Trailer":
            return f"https://www.youtube.com/watch?v={video['key']}"
    return None
