import logging

from mcp_servers.tmdb_mcp.server import mcp

# Com a API Key v3 a chave vai no URL, e o httpx regista cada URL ao nível INFO.
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp.run("stdio")
