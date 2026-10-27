import functools
from collections.abc import Awaitable, Callable
from typing import Any

from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError
from mcp_servers.lastfm_mcp.service.lastfm_input import InvalidInputError

_API_ERROR_KINDS = {10: "invalid_api_key", 26: "invalid_api_key", 29: "rate_limited"}


def lastfm_operation(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[dict]]:
    """Converte o resultado/exceções de um método de service no formato
    {"success": True, "data": ...} ou {"success": False, "error": <código>, "detail": ...}.

    Um método que devolve None significa 'o Last.fm não encontrou o recurso'.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            data = await func(*args, **kwargs)
        except InvalidInputError as exc:
            return {"success": False, "error": "invalid_input", "detail": str(exc)}
        except LastFmApiError as exc:
            kind = _API_ERROR_KINDS.get(exc.code, "lastfm_error")
            return {"success": False, "error": kind, "detail": exc.message or f"código {exc.code}"}
        except LastFmUnavailableError as exc:
            return {"success": False, "error": "unavailable", "detail": exc.reason}
        if data is None:
            return {"success": False, "error": "not_found"}
        return {"success": True, "data": data}

    return wrapper
