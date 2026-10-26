import sys
from pathlib import Path

from config import user_settings
from data.model.mcp_model import McpServerConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def builtin_server_configs() -> list[McpServerConfig]:
    servers = []
    tmdb_api_key = user_settings.get_tmdb_api_key()
    if tmdb_api_key:
        servers.append(McpServerConfig(
            name="tmdb",
            command=sys.executable,
            args=["-m", "mcp_servers.tmdb_mcp"],
            cwd=str(PROJECT_ROOT),
            env={"TMDB_API_KEY": tmdb_api_key},
            trusted=True,
        ))
    return servers
