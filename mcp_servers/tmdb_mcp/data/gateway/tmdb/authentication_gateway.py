import httpx

from mcp_servers.tmdb_mcp.config.connections.tmdb_connection import TmdbConnect
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import TmdbUnavailableError


class AuthenticationGateway:
    @staticmethod
    async def is_key_valid(api_key: str) -> bool:
        try:
            async with TmdbConnect.new_client(api_key) as client:
                response = await client.get("/authentication")
        except httpx.HTTPError as exc:
            raise TmdbUnavailableError(type(exc).__name__) from exc
        if response.status_code == 401:
            return False
        if response.is_error:
            raise TmdbUnavailableError(f"HTTP {response.status_code}")
        return True
