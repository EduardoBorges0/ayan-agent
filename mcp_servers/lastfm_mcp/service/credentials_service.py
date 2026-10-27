from mcp_servers.lastfm_mcp.data.gateway.authentication_gateway import AuthenticationGateway
from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError, LastFmUnavailableError


class CredentialsService:
    @staticmethod
    async def validate_key(api_key: str) -> dict:
        api_key = api_key.strip()
        if not api_key:
            return {"success": False, "error": "empty_key"}
        try:
            valid = await AuthenticationGateway.is_key_valid(api_key)
        except LastFmUnavailableError as exc:
            return {"success": False, "error": "lastfm_unavailable", "detail": exc.reason}
        except LastFmApiError as exc:
            return {"success": False, "error": "lastfm_unavailable", "detail": exc.message or f"código {exc.code}"}
        if not valid:
            return {"success": False, "error": "invalid_key"}
        return {"success": True, "data": api_key}
