import logging

from mcp_servers.lastfm_mcp.server import mcp

# A chave API vai no URL de cada pedido e o httpx regista cada URL ao nível INFO,
# o que a deixaria escrita no ficheiro de log do servidor.
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp.run("stdio")
