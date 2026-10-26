from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from data.gateway.mcp_gateway import McpUnavailableError
from data.model.agent_model import ToolContext
from data.model.mcp_model import McpCallResult, McpServerConfig, McpToolInfo
from service.agent.computer_tools import REFUSED
from service.agent.mcp_tools import MAX_MCP_OUTPUT_CHARS, McpToolsService

SEARCH = McpToolInfo(server="tmdb", name="search_movies", description="Pesquisa filmes.", input_schema={
    "type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"],
})


def _context(approve: bool = True) -> tuple[ToolContext, MagicMock]:
    confirm = MagicMock(return_value=approve)
    return ToolContext(workspace=Path("."), confirm=confirm), confirm


USER_TMDB = McpServerConfig(name="tmdb", command="python")
BUILTIN_TMDB = McpServerConfig(name="tmdb", command="python", args=["-m", "mcp_servers.tmdb_mcp"], trusted=True)


async def _connect_and_capture(mock_gateway, *infos: McpToolInfo, user=(USER_TMDB,), builtin=()):
    mock_gateway.list_tools = AsyncMock(return_value=list(infos))
    with patch("service.agent.mcp_tools.load_server_configs", return_value=(list(user), [])), \
         patch("service.agent.mcp_tools.builtin_server_configs", return_value=list(builtin)), \
         patch("service.agent.mcp_tools.McpConnect") as mock_connect:
        mock_connect.start = AsyncMock(return_value={})
        connection = (await McpToolsService.connect())["data"]
        return connection, mock_connect.start.call_args.args[0]


async def _connect_with(mock_gateway, *infos: McpToolInfo, user=(USER_TMDB,), builtin=()):
    connection, _ = await _connect_and_capture(mock_gateway, *infos, user=user, builtin=builtin)
    return connection


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_connect_exposes_tools_with_server_prefix_and_schema(mock_gateway):
    connection = await _connect_with(mock_gateway, SEARCH)

    tool = connection.tools[0]
    assert tool.definition.name == "tmdb__search_movies"
    assert tool.definition.description == "[MCP tmdb] Pesquisa filmes."
    assert tool.definition.parameters == SEARCH.input_schema
    assert connection.servers == {"tmdb": 1}


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_connect_skips_tools_whose_name_the_model_would_reject(mock_gateway):
    bad = McpToolInfo(server="tmdb", name="pesquisa de filmes", description="", input_schema={})

    connection = await _connect_with(mock_gateway, SEARCH, bad)

    assert [tool.definition.name for tool in connection.tools] == ["tmdb__search_movies"]
    assert "pesquisa de filmes" in connection.warnings[0]


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_builtin_server_is_started_when_user_has_none_with_that_name(mock_gateway):
    _, started = await _connect_and_capture(mock_gateway, SEARCH, user=(), builtin=(BUILTIN_TMDB,))

    assert started == [BUILTIN_TMDB]


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_user_configured_server_overrides_builtin_with_same_name(mock_gateway):
    _, started = await _connect_and_capture(mock_gateway, SEARCH, user=(USER_TMDB,), builtin=(BUILTIN_TMDB,))

    assert started == [USER_TMDB]


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_tools_of_trusted_builtin_servers_never_ask_for_approval(mock_gateway):
    tool = (await _connect_with(mock_gateway, SEARCH, user=(), builtin=(BUILTIN_TMDB,))).tools[0]
    mock_gateway.call_tool = AsyncMock(return_value=McpCallResult(text="Matrix (1999)", is_error=False))
    context, confirm = _context(approve=False)

    outcome = await tool.run('{"query": "matrix"}', context)

    assert outcome.output == "Matrix (1999)"
    confirm.assert_not_called()


@pytest.mark.asyncio
async def test_connect_reports_servers_that_failed_to_start():
    with patch("service.agent.mcp_tools.load_server_configs",
               return_value=([McpServerConfig(name="tmdb", command="nao-existe")], [])), \
         patch("service.agent.mcp_tools.builtin_server_configs", return_value=[]), \
         patch("service.agent.mcp_tools.McpConnect") as mock_connect:
        mock_connect.start = AsyncMock(return_value={"tmdb": "FileNotFoundError: nao-existe"})
        connection = (await McpToolsService.connect())["data"]

    assert connection.tools == []
    assert connection.warnings == ["Não consegui ligar ao servidor MCP 'tmdb': FileNotFoundError: nao-existe"]


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_tool_asks_approval_only_on_first_use_in_the_session(mock_gateway):
    tool = (await _connect_with(mock_gateway, SEARCH)).tools[0]
    mock_gateway.call_tool = AsyncMock(return_value=McpCallResult(text="Matrix (1999)", is_error=False))
    context, confirm = _context(approve=True)

    first = await tool.run('{"query": "matrix"}', context)
    await tool.run('{"query": "dune"}', context)

    assert first.output == "Matrix (1999)"
    assert first.event == "Usei tmdb.search_movies"
    confirm.assert_called_once()
    assert '"query": "matrix"' in confirm.call_args.args[0]
    mock_gateway.call_tool.assert_awaited_with("tmdb", "search_movies", {"query": "dune"})


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_refused_tool_is_never_called_nor_remembered(mock_gateway):
    tool = (await _connect_with(mock_gateway, SEARCH)).tools[0]
    mock_gateway.call_tool = AsyncMock()
    context, _ = _context(approve=False)

    outcome = await tool.run('{"query": "matrix"}', context)

    assert outcome.output == REFUSED
    assert context.approved_tools == set()
    mock_gateway.call_tool.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ["não é json", "[1, 2]"])
@patch("service.agent.mcp_tools.McpGateway")
async def test_invalid_arguments_are_rejected_before_asking(mock_gateway, arguments):
    tool = (await _connect_with(mock_gateway, SEARCH)).tools[0]
    context, confirm = _context()

    outcome = await tool.run(arguments, context)

    assert outcome.output == "Erro: argumentos inválidos."
    confirm.assert_not_called()


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_server_errors_are_reported_to_model_and_user(mock_gateway):
    tool = (await _connect_with(mock_gateway, SEARCH)).tools[0]
    context, _ = _context()

    mock_gateway.call_tool = AsyncMock(return_value=McpCallResult(text="Token inválido", is_error=True))
    tool_error = await tool.run('{"query": "x"}', context)
    mock_gateway.call_tool = AsyncMock(side_effect=McpUnavailableError("o servidor fechou"))
    transport_error = await tool.run('{"query": "x"}', context)

    assert tool_error.output == "A ferramenta devolveu um erro: Token inválido"
    assert tool_error.event == "tmdb.search_movies devolveu um erro"
    assert "o servidor fechou" in transport_error.output


@pytest.mark.asyncio
@patch("service.agent.mcp_tools.McpGateway")
async def test_long_results_are_truncated(mock_gateway):
    tool = (await _connect_with(mock_gateway, SEARCH)).tools[0]
    mock_gateway.call_tool = AsyncMock(return_value=McpCallResult(text="x" * (MAX_MCP_OUTPUT_CHARS + 10), is_error=False))
    context, _ = _context()

    outcome = await tool.run('{"query": "x"}', context)

    assert outcome.output.endswith(f"[Resposta truncada: {MAX_MCP_OUTPUT_CHARS + 10} caracteres no total.]")
