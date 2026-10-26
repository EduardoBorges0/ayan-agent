import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from data.model.agent_model import ToolContext
from data.model.mcp_model import McpServerConfig
from service.agent.mcp_tools import McpToolsService

SERVER_SCRIPT = '''
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer(name="teste")


@mcp.tool()
def echo(text: str) -> str:
    """Devolve o texto recebido."""
    return f"eco: {text}"


@mcp.tool()
def fail() -> str:
    """Falha sempre."""
    raise ToolError("falhou de propósito")


mcp.run("stdio")
'''


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_tools_talk_to_a_real_stdio_mcp_server(tmp_path, monkeypatch):
    script = tmp_path / "server.py"
    script.write_text(SERVER_SCRIPT, encoding="utf-8")
    servers = [
        McpServerConfig(name="teste", command=sys.executable, args=[str(script)]),
        McpServerConfig(name="partido", command="comando-que-nao-existe-ayan"),
    ]
    monkeypatch.setattr("service.agent.mcp_tools.load_server_configs", lambda: (servers, []))
    monkeypatch.setattr("config.connections.mcp_connection.USER_CONFIG_DIR", tmp_path)

    connection = (await McpToolsService.connect())["data"]
    try:
        assert connection.servers == {"teste": 2}
        assert len(connection.warnings) == 1 and "'partido'" in connection.warnings[0]

        tools = {tool.definition.name: tool for tool in connection.tools}
        context = ToolContext(workspace=Path(tmp_path), confirm=MagicMock(return_value=True))

        echo = await tools["teste__echo"].run('{"text": "olá"}', context)
        failure = await tools["teste__fail"].run("{}", context)
    finally:
        await McpToolsService.disconnect()

    assert echo.output == "eco: olá"
    assert "falhou de propósito" in failure.output
    assert failure.event == "teste.fail devolveu um erro"
