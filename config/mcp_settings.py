import json

from pydantic import ValidationError

from data.model.mcp_model import McpServerConfig
from load_env import MCP_CONFIG_PATH


class McpConfigError(Exception):
    pass


def _read() -> dict:
    if not MCP_CONFIG_PATH.exists():
        return {"mcpServers": {}}
    try:
        data = json.loads(MCP_CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise McpConfigError(f"{MCP_CONFIG_PATH} não é um JSON válido: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.setdefault("mcpServers", {}), dict):
        raise McpConfigError(f"{MCP_CONFIG_PATH} tem de ter um objeto 'mcpServers'.")
    return data


def _write(data: dict) -> None:
    MCP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_server_configs() -> tuple[list[McpServerConfig], list[str]]:
    try:
        raw_servers = _read()["mcpServers"]
    except McpConfigError as exc:
        return [], [str(exc)]

    servers, warnings = [], []
    for name, raw in raw_servers.items():
        try:
            servers.append(McpServerConfig(name=name, **raw))
        except (ValidationError, TypeError) as exc:
            warnings.append(f"O servidor MCP '{name}' está mal configurado em {MCP_CONFIG_PATH}: {exc}")
    return servers, warnings


def add_server(server: McpServerConfig) -> None:
    data = _read()
    data["mcpServers"][server.name] = server.model_dump(exclude={"name"}, exclude_defaults=True)
    _write(data)


def remove_server(name: str) -> bool:
    data = _read()
    if data["mcpServers"].pop(name, None) is None:
        return False
    _write(data)
    return True
