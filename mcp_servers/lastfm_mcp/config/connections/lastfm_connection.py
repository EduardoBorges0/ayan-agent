import asyncio

import httpx

from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError
from mcp_servers.lastfm_mcp.load_env import (
    LASTFM_API_KEY,
    LASTFM_BASE_URL,
    LASTFM_MAX_ATTEMPTS,
    LASTFM_RETRY_BACKOFF_SECONDS,
    LASTFM_TIMEOUT_SECONDS,
    LASTFM_USER_AGENT,
)

INVALID_API_KEY_CODE = 10
_NOT_FOUND_CODES = {6, 7}
_TRANSIENT_CODES = {8, 11, 16}


def _json_or_none(response: httpx.Response) -> object | None:
    try:
        return response.json()
    except ValueError:
        return None


def _error_code(raw: object) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


class LastFmConnect:
    """Ligação física ao Last.fm: cliente HTTP partilhado, chave API, timeout e retry.

    Os gateways usam apenas `request`; nunca constroem URLs nem veem a chave API.
    """

    _client: httpx.AsyncClient | None = None

    @classmethod
    def _client_instance(cls) -> httpx.AsyncClient:
        if cls._client is None or cls._client.is_closed:
            cls._client = httpx.AsyncClient(
                timeout=LASTFM_TIMEOUT_SECONDS,
                headers={"User-Agent": LASTFM_USER_AGENT},
            )
        return cls._client

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None

    @classmethod
    async def request(cls, method: str, params: dict[str, str | int], api_key: str | None = None) -> dict | None:
        """Chama um método da API. Devolve None se o recurso não existe; levanta
        LastFmApiError (erro da API) ou LastFmUnavailableError (sem resposta utilizável).

        `api_key` só é passado ao validar uma chave ainda não guardada (ayan config);
        nas chamadas normais usa-se a chave recebida do ambiente.

        As mensagens de erro nunca incluem o URL do pedido, porque este leva a chave API.
        """
        key = api_key or LASTFM_API_KEY
        if not key:
            raise LastFmApiError(INVALID_API_KEY_CODE, "A variável de ambiente LASTFM_API_KEY não está definida.")

        query = {**params, "method": method, "api_key": key, "format": "json"}
        reason = "sem resposta"
        for attempt in range(1, LASTFM_MAX_ATTEMPTS + 1):
            try:
                response = await cls._client_instance().get(LASTFM_BASE_URL, params=query)
            except httpx.TransportError as exc:
                reason = f"falha de rede ({type(exc).__name__})"
            else:
                payload = _json_or_none(response)
                if isinstance(payload, dict) and "error" in payload:
                    code = _error_code(payload["error"])
                    if code in _NOT_FOUND_CODES:
                        return None
                    if code not in _TRANSIENT_CODES:
                        raise LastFmApiError(code, str(payload.get("message", "")))
                    reason = f"o Last.fm está temporariamente indisponível (código {code})"
                elif response.status_code >= 500:
                    reason = f"o Last.fm respondeu HTTP {response.status_code}"
                elif response.status_code >= 400 or not isinstance(payload, dict):
                    raise LastFmUnavailableError(f"resposta inesperada do Last.fm (HTTP {response.status_code})")
                else:
                    return payload
            if attempt < LASTFM_MAX_ATTEMPTS:
                await asyncio.sleep(LASTFM_RETRY_BACKOFF_SECONDS * attempt)
        raise LastFmUnavailableError(reason)
