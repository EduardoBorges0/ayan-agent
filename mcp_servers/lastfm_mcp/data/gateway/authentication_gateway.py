from mcp_servers.lastfm_mcp.config.connections.lastfm_connection import LastFmConnect
from mcp_servers.lastfm_mcp.data.model.lastfm_errors import LastFmApiError

_REJECTED_KEY_CODES = {10, 26}


class AuthenticationGateway:
    @staticmethod
    async def is_key_valid(api_key: str) -> bool:
        """O Last.fm não tem um método só para validar chaves: uma pesquisa mínima de artista
        serve, porque uma chave inválida ou suspensa é recusada antes de qualquer pesquisa.

        Levanta LastFmUnavailableError se o Last.fm não puder ser contactado.
        """
        try:
            await LastFmConnect.request("artist.search", {"artist": "a", "limit": 1}, api_key=api_key)
        except LastFmApiError as exc:
            if exc.code in _REJECTED_KEY_CODES:
                return False
            raise
        finally:
            await LastFmConnect.close()
        return True
