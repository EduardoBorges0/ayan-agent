from collections.abc import Awaitable

from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import TmdbAuthError, TmdbUnavailableError

MAX_QUERY_LENGTH = 200


def clean_query(query: str) -> tuple[str, str | None]:
    query = " ".join(query.split())
    if not query:
        return query, "empty_query"
    if len(query) > MAX_QUERY_LENGTH:
        return query, "query_too_long"
    return query, None


async def tmdb_call(request: Awaitable) -> dict:
    try:
        data = await request
    except TmdbAuthError as exc:
        return {"success": False, "error": "tmdb_auth_failed", "detail": exc.reason}
    except TmdbUnavailableError as exc:
        return {"success": False, "error": "tmdb_unavailable", "detail": exc.reason}
    if data is None:
        return {"success": False, "error": "not_found"}
    return {"success": True, "data": data}
