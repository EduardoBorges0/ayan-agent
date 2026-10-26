import json
import re

from config.connections.mcp_connection import McpConnect
from config.mcp_settings import load_server_configs
from data.gateway.mcp_gateway import McpGateway, McpUnavailableError
from data.model.agent_model import AgentTool, ToolContext, ToolDefinition, ToolOutcome
from data.model.mcp_model import McpConnection, McpToolInfo
from service.agent.computer_tools import REFUSED

MAX_MCP_OUTPUT_CHARS = 20_000
MAX_ARGUMENTS_PREVIEW_CHARS = 300
_VALID_TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def qualified_tool_name(server: str, tool: str) -> str:
    return f"{server}__{tool}"


def _truncate(text: str) -> str:
    if len(text) <= MAX_MCP_OUTPUT_CHARS:
        return text
    return text[:MAX_MCP_OUTPUT_CHARS] + f"\n[Resposta truncada: {len(text)} caracteres no total.]"


def _preview(arguments: dict) -> str:
    text = json.dumps(arguments, ensure_ascii=False)
    return text if len(text) <= MAX_ARGUMENTS_PREVIEW_CHARS else text[:MAX_ARGUMENTS_PREVIEW_CHARS] + "…"


def _to_agent_tool(info: McpToolInfo) -> AgentTool | None:
    name = qualified_tool_name(info.server, info.name)
    if not _VALID_TOOL_NAME.match(name):
        return None
    label = f"{info.server}.{info.name}"

    async def run(arguments: str, context: ToolContext) -> ToolOutcome:
        try:
            parsed = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            parsed = None
        if not isinstance(parsed, dict):
            return ToolOutcome("Erro: argumentos inválidos.")

        if name not in context.approved_tools:
            if not context.confirm(
                f"usar a ferramenta '{info.name}' do servidor MCP '{info.server}' durante esta sessão\n"
                f"    Argumentos deste pedido: {_preview(parsed)}"
            ):
                return ToolOutcome(REFUSED, f"Recusaste {label}")
            context.approved_tools.add(name)

        try:
            result = await McpGateway.call_tool(info.server, info.name, parsed)
        except McpUnavailableError as exc:
            return ToolOutcome(
                f"Erro ao contactar o servidor MCP '{info.server}': {exc.reason}",
                f"Não consegui usar {label}: {exc.reason}",
            )
        if result.is_error:
            return ToolOutcome(f"A ferramenta devolveu um erro: {_truncate(result.text)}", f"{label} devolveu um erro")
        return ToolOutcome(_truncate(result.text), f"Usei {label}")

    return AgentTool(
        ToolDefinition(
            name=name,
            description=f"[MCP {info.server}] {info.description}",
            parameters=info.input_schema or {"type": "object", "properties": {}},
        ),
        run,
    )


class McpToolsService:
    @staticmethod
    async def connect() -> dict:
        configs, warnings = load_server_configs()
        if not configs:
            return {"success": True, "data": McpConnection(warnings=warnings)}

        failures = await McpConnect.start(configs)
        warnings += [f"Não consegui ligar ao servidor MCP '{name}': {reason}" for name, reason in failures.items()]

        tools: list[AgentTool] = []
        servers: dict[str, int] = {}
        for config in configs:
            if config.name in failures:
                continue
            try:
                infos = await McpGateway.list_tools(config.name)
            except McpUnavailableError as exc:
                warnings.append(f"Não consegui listar as ferramentas do servidor MCP '{config.name}': {exc.reason}")
                continue
            servers[config.name] = 0
            for info in infos:
                tool = _to_agent_tool(info)
                if tool is None:
                    warnings.append(f"Ignorei a ferramenta '{info.name}' de '{config.name}': o nome não é aceite pelo modelo.")
                    continue
                tools.append(tool)
                servers[config.name] += 1

        return {"success": True, "data": McpConnection(tools=tools, servers=servers, warnings=warnings)}

    @staticmethod
    async def disconnect() -> None:
        await McpConnect.stop()
