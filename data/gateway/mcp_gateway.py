import json

from mcp import ClientSession
from mcp.types import CallToolResult, PaginatedRequestParams, TextContent

from config.connections.mcp_connection import McpConnect, describe_error
from data.model.mcp_model import McpCallResult, McpToolInfo


class McpUnavailableError(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _session(server: str) -> ClientSession:
    session = McpConnect.get_session(server)
    if session is None:
        raise McpUnavailableError(f"o servidor '{server}' não está ligado")
    return session


def _content_text(result: CallToolResult) -> str:
    parts = [
        item.text if isinstance(item, TextContent) else f"[conteúdo do tipo {item.type} omitido]"
        for item in result.content
    ]
    if not parts and result.structured_content is not None:
        parts.append(json.dumps(result.structured_content, ensure_ascii=False))
    return "\n".join(parts)


class McpGateway:
    @staticmethod
    async def list_tools(server: str) -> list[McpToolInfo]:
        session = _session(server)
        tools, cursor = [], None
        try:
            while True:
                result = await session.list_tools(params=PaginatedRequestParams(cursor=cursor) if cursor else None)
                tools.extend(result.tools)
                cursor = result.next_cursor
                if not cursor:
                    break
        except Exception as exc:
            raise McpUnavailableError(describe_error(exc)) from exc
        return [
            McpToolInfo(server=server, name=tool.name, description=tool.description or "", input_schema=tool.input_schema)
            for tool in tools
        ]

    @staticmethod
    async def call_tool(server: str, tool: str, arguments: dict) -> McpCallResult:
        session = _session(server)
        try:
            result = await session.call_tool(tool, arguments)
        except Exception as exc:
            raise McpUnavailableError(describe_error(exc)) from exc
        if not isinstance(result, CallToolResult):
            return McpCallResult(text="O servidor pediu interação adicional, que o ayan ainda não suporta.", is_error=True)
        return McpCallResult(text=_content_text(result), is_error=bool(result.is_error))
