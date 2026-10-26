from mcp_servers.tmdb_mcp.data.gateway.tmdb.authentication_gateway import AuthenticationGateway
from mcp_servers.tmdb_mcp.data.gateway.tmdb.tmdb_api import TmdbUnavailableError


class CredentialsService:
    @staticmethod
    async def validate_key(api_key: str) -> dict:
        api_key = api_key.strip()
        if not api_key:
            return {"success": False, "error": "empty_key"}
        try:
            valid = await AuthenticationGateway.is_key_valid(api_key)
        except TmdbUnavailableError as exc:
            return {"success": False, "error": "tmdb_unavailable", "detail": exc.reason}
        if not valid:
            return {"success": False, "error": "invalid_key"}
        return {"success": True, "data": api_key}
