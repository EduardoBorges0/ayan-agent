import asyncio
from pathlib import Path

from pydantic import BaseModel

from data.gateway.filesystem_gateway import FilesystemGateway
from data.gateway.powershell_gateway import PowerShellGateway
from data.model.agent_model import AgentTool, ToolContext, ToolDefinition, ToolOutcome
from data.model.computer_model import CommandResult
from load_env import AGENT_COMMAND_TIMEOUT_SECONDS

MAX_FILE_BYTES = 100_000
MAX_DIRECTORY_ENTRIES = 200
MAX_COMMAND_OUTPUT_CHARS = 20_000

REFUSED = "O utilizador recusou esta ação. Não a repitas; pergunta-lhe como prefere avançar."


class _PathArgs(BaseModel):
    path: str


class _CommandArgs(BaseModel):
    command: str


def _resolve(path_text: str, workspace: Path) -> Path:
    path = Path(path_text).expanduser()
    return (path if path.is_absolute() else workspace / path).resolve()


def _allowed_outside_workspace(path: Path, context: ToolContext, action: str) -> bool:
    if path.is_relative_to(context.workspace.resolve()):
        return True
    return context.confirm(f"{action} fora da pasta atual:\n    {path}")


def _decode(data: bytes, truncated: bool) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        if truncated and exc.start >= len(data) - 3:
            return data[:exc.start].decode("utf-8-sig")
        return data.decode("cp1252", errors="replace")


def _truncate(text: str) -> str:
    if len(text) <= MAX_COMMAND_OUTPUT_CHARS:
        return text
    return text[:MAX_COMMAND_OUTPUT_CHARS] + f"\n[Saída truncada: {len(text)} caracteres no total.]"


async def _read_file(arguments: str, context: ToolContext) -> ToolOutcome:
    path = _resolve(_PathArgs.model_validate_json(arguments).path, context.workspace)
    if not _allowed_outside_workspace(path, context, "ler um ficheiro"):
        return ToolOutcome(REFUSED, f"Recusaste a leitura de {path}")
    try:
        content = await asyncio.to_thread(FilesystemGateway.read_bytes, path, MAX_FILE_BYTES)
    except OSError as exc:
        return ToolOutcome(f"Erro ao ler {path}: {exc.strerror or exc}")
    if b"\x00" in content.data:
        return ToolOutcome(f"Erro: {path} parece ser um ficheiro binário e não pode ser lido como texto.")

    truncated = content.total_size > MAX_FILE_BYTES
    text = _decode(content.data, truncated)
    if truncated:
        text += f"\n[Ficheiro truncado: mostrados {MAX_FILE_BYTES} de {content.total_size} bytes.]"
    return ToolOutcome(text, f"Li {path}")


async def _list_directory(arguments: str, context: ToolContext) -> ToolOutcome:
    path = _resolve(_PathArgs.model_validate_json(arguments).path, context.workspace)
    if not _allowed_outside_workspace(path, context, "listar uma pasta"):
        return ToolOutcome(REFUSED, f"Recusaste a listagem de {path}")
    try:
        entries = await asyncio.to_thread(FilesystemGateway.list_directory, path)
    except OSError as exc:
        return ToolOutcome(f"Erro ao listar {path}: {exc.strerror or exc}")

    entries.sort(key=lambda entry: (not entry.is_dir, entry.name.casefold()))
    lines = [
        f"[pasta] {entry.name}" if entry.is_dir else f"{entry.name} ({entry.size} bytes)"
        for entry in entries[:MAX_DIRECTORY_ENTRIES]
    ]
    if len(entries) > MAX_DIRECTORY_ENTRIES:
        lines.append(f"... e mais {len(entries) - MAX_DIRECTORY_ENTRIES} entradas.")
    listing = "\n".join(lines) if lines else "(pasta vazia)"
    return ToolOutcome(f"Conteúdo de {path}:\n{listing}", f"Listei {path}")


def _format_command_result(result: CommandResult) -> tuple[str, str]:
    if result.timed_out:
        status = f"O comando foi interrompido ao fim de {AGENT_COMMAND_TIMEOUT_SECONDS} segundos."
    else:
        status = f"O comando terminou com o código {result.exit_code}."
    parts = [status]
    if result.stdout.strip():
        parts.append(f"Saída:\n{_truncate(result.stdout)}")
    if result.stderr.strip():
        parts.append(f"Erros:\n{_truncate(result.stderr)}")
    return "\n".join(parts), status


async def _run_powershell(arguments: str, context: ToolContext) -> ToolOutcome:
    command = _CommandArgs.model_validate_json(arguments).command.strip()
    if not command:
        return ToolOutcome("Erro: o comando está vazio.")
    if not context.confirm(f"executar no PowerShell (em {context.workspace}):\n    {command}"):
        return ToolOutcome(REFUSED, "Recusaste o comando.")
    try:
        result = await asyncio.to_thread(
            PowerShellGateway.run, command, context.workspace, AGENT_COMMAND_TIMEOUT_SECONDS
        )
    except OSError as exc:
        return ToolOutcome(f"Erro ao iniciar o PowerShell: {exc.strerror or exc}")
    output, status = _format_command_result(result)
    return ToolOutcome(output, status)


_PATH_PARAMETERS = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Caminho absoluto ou relativo à pasta atual. Usa '.' para a própria pasta atual.",
        },
    },
    "required": ["path"],
    "additionalProperties": False,
}

COMPUTER_TOOLS = [
    AgentTool(
        ToolDefinition(
            name="read_file",
            description="Lê um ficheiro de texto do computador do utilizador.",
            parameters=_PATH_PARAMETERS,
        ),
        _read_file,
    ),
    AgentTool(
        ToolDefinition(
            name="list_directory",
            description="Lista o conteúdo de uma pasta do computador do utilizador.",
            parameters=_PATH_PARAMETERS,
        ),
        _list_directory,
    ),
    AgentTool(
        ToolDefinition(
            name="run_powershell",
            description=(
                "Executa um comando no Windows PowerShell, na pasta atual. O utilizador tem de aprovar "
                "cada comando antes de ele correr."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando PowerShell a executar."},
                },
                "required": ["command"],
                "additionalProperties": False,
            },
        ),
        _run_powershell,
    ),
]
