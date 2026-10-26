from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import CallToolResult, ImageContent, ListToolsResult, TextContent, Tool

from data.gateway.mcp_gateway import McpGateway, McpUnavailableError


def _session(**methods) -> MagicMock:
    session = MagicMock()
    for name, mock in methods.items():
        setattr(session, name, mock)
    return session


@pytest.mark.asyncio
@patch("data.gateway.mcp_gateway.McpConnect")
async def test_list_tools_follows_pagination(mock_connect):
    mock_connect.get_session.return_value = _session(list_tools=AsyncMock(side_effect=[
        ListToolsResult(tools=[Tool(name="a", description="A", input_schema={"type": "object"})], next_cursor="p2"),
        ListToolsResult(tools=[Tool(name="b", input_schema={"type": "object"})], next_cursor=None),
    ]))

    tools = await McpGateway.list_tools("tmdb")

    assert [(tool.server, tool.name, tool.description) for tool in tools] == [("tmdb", "a", "A"), ("tmdb", "b", "")]


@pytest.mark.asyncio
@patch("data.gateway.mcp_gateway.McpConnect")
async def test_call_tool_joins_text_and_marks_other_content(mock_connect):
    mock_connect.get_session.return_value = _session(call_tool=AsyncMock(return_value=CallToolResult(
        content=[
            TextContent(type="text", text="Matrix (1999)"),
            ImageContent(type="image", data="aGVsbG8=", mime_type="image/png"),
        ],
        is_error=False,
    )))

    result = await McpGateway.call_tool("tmdb", "search_movies", {"query": "matrix"})

    assert result.text == "Matrix (1999)\n[conteúdo do tipo image omitido]"
    assert result.is_error is False
    mock_connect.get_session.return_value.call_tool.assert_awaited_once_with("search_movies", {"query": "matrix"})


@pytest.mark.asyncio
@patch("data.gateway.mcp_gateway.McpConnect")
async def test_call_tool_uses_structured_content_when_there_is_no_text(mock_connect):
    mock_connect.get_session.return_value = _session(call_tool=AsyncMock(return_value=CallToolResult(
        content=[], structured_content={"total": 3}, is_error=False,
    )))

    result = await McpGateway.call_tool("tmdb", "x", {})

    assert result.text == '{"total": 3}'


@pytest.mark.asyncio
@patch("data.gateway.mcp_gateway.McpConnect")
async def test_transport_failure_raises_unavailable(mock_connect):
    mock_connect.get_session.return_value = _session(call_tool=AsyncMock(side_effect=ConnectionResetError("fechou")))

    with pytest.raises(McpUnavailableError) as raised:
        await McpGateway.call_tool("tmdb", "x", {})

    assert raised.value.reason == "ConnectionResetError: fechou"


@pytest.mark.asyncio
@patch("data.gateway.mcp_gateway.McpConnect")
async def test_server_not_connected_raises_unavailable(mock_connect):
    mock_connect.get_session.return_value = None

    with pytest.raises(McpUnavailableError):
        await McpGateway.list_tools("tmdb")
