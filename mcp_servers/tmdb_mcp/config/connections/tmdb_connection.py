import httpx

from mcp_servers.tmdb_mcp.config.credentials import get_api_key
from mcp_servers.tmdb_mcp.load_env import TMDB_TIMEOUT_SECONDS

TMDB_BASE_URL = "https://api.themoviedb.org/3"


def is_read_access_token(api_key: str) -> bool:
    return api_key.startswith("eyJ") and api_key.count(".") == 2


class TmdbConnect:
    _client: httpx.AsyncClient | None = None

    @staticmethod
    def new_client(api_key: str) -> httpx.AsyncClient:
        headers = {"Accept": "application/json"}
        params = {}
        if is_read_access_token(api_key):
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            params["api_key"] = api_key
        return httpx.AsyncClient(
            base_url=TMDB_BASE_URL,
            headers=headers,
            params=params,
            timeout=TMDB_TIMEOUT_SECONDS,
            transport=httpx.AsyncHTTPTransport(retries=2),
        )

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._client is None:
            cls._client = cls.new_client(get_api_key())
        return cls._client
