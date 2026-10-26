from mcp_servers.tmdb_mcp.load_env import TMDB_API_KEY


class MissingTokenError(Exception):
    pass


def get_api_key() -> str:
    if not TMDB_API_KEY:
        raise MissingTokenError("A chave do TMDB não está configurada. Corre: ayan config")
    return TMDB_API_KEY
