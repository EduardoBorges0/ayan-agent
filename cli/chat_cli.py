import argparse
import asyncio
import getpass
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from config import mcp_settings, user_settings
from config.connections.openai_connection import OpenAIConnect
from data.model.agent_model import ToolContext
from data.model.chat_model import MAX_HISTORY_MESSAGES, ChatMessage
from data.model.mcp_model import McpServerConfig
from load_env import MCP_CONFIG_PATH
from mcp_servers.lastfm_mcp.service.credentials_service import CredentialsService as LastFmCredentialsService
from mcp_servers.tmdb_mcp.service.credentials_service import CredentialsService as TmdbCredentialsService
from service.agent.agent_service import AgentService
from service.agent.computer_tools import initial_approved_folders
from service.agent.mcp_tools import McpToolsService
from service.chat_service import ChatService
from service.memory_service import MemoryService
from utils.logging_config import configure_logging

EXIT_COMMANDS = {"/sair", "/exit"}
CLEAR_COMMAND = "/limpar"
MEMORY_COMMAND = "/memoria"
FORGET_COMMAND = "/esquecer"
MCP_COMMAND = "/mcp"
WELCOME_TEXT = (
    "Escreve a tua mensagem. Comandos: /memoria (ver o que sei sobre ti), /esquecer N (apagar a memória N), "
    "/mcp (ferramentas MCP ligadas), /limpar (nova conversa), /sair (terminar)."
)

_ERROR_MESSAGES = {
    "llm_auth_failed": "A OpenAI rejeitou a chave API. Corre 'ayan config' para a alterar.",
    "llm_unavailable": "Não foi possível obter resposta da OpenAI.",
    "empty_reply": "A OpenAI não devolveu resposta. Tenta reformular a mensagem.",
}

Runner = Callable[[Coroutine[Any, Any, dict]], dict]


def _error_text(result: dict) -> str:
    text = _ERROR_MESSAGES[result["error"]]
    if result.get("detail"):
        text += f"\nMotivo indicado pela OpenAI: {result['detail']}"
    return text


def confirm_action(
    description: str,
    read_line: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> bool:
    write(f"\n  O agente quer {description}")
    answer = read_line("  Permitir? [s/N]: ").replace("\ufeff", "").strip().lower()
    return answer in {"s", "sim"}


def run_chat(
    read_line: Callable[[str], str], write: Callable[[str], None], run: Runner, context: ToolContext
) -> None:
    history: list[ChatMessage] = []
    write(WELCOME_TEXT)
    while True:
        try:
            text = read_line("\nTu: ").replace("\ufeff", "").strip()
        except EOFError:
            return
        if not text:
            continue
        if text.lower() in EXIT_COMMANDS:
            return
        if text.lower() == CLEAR_COMMAND:
            history.clear()
            write("Conversa limpa.")
            continue
        if text.lower() == MEMORY_COMMAND:
            _show_memories(write, run)
            continue
        if text.lower().split()[0] == FORGET_COMMAND:
            _forget_memory(text, write, run)
            continue
        if text.lower() == MCP_COMMAND:
            _show_mcp_tools(write, context)
            continue

        try:
            history.append(ChatMessage(role="user", content=text))
        except ValidationError:
            write("Mensagem demasiado longa. Divide-a em partes mais pequenas.")
            continue

        result = run(AgentService.reply(history[-MAX_HISTORY_MESSAGES:], context))
        if not result["success"]:
            history.pop()
            write(_error_text(result))
            continue

        for event in result["data"].events:
            write(f"  · {event}")
        reply = result["data"].reply
        # O limite de tamanho do ChatMessage protege o input do utilizador, não a resposta do modelo.
        history.append(ChatMessage.model_construct(role="assistant", content=reply))
        write(f"\nAyan: {reply}")


def _show_memories(write: Callable[[str], None], run: Runner) -> None:
    memories = run(MemoryService.list_memories())["data"]
    if not memories:
        write("Ainda não guardei nada sobre ti.")
        return
    write("O que sei sobre ti:")
    for memory in memories:
        write(f"  {memory.id:>3}) {memory.content}")


def _forget_memory(text: str, write: Callable[[str], None], run: Runner) -> None:
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        write("Usa: /esquecer N (o número aparece em /memoria).")
        return
    result = run(MemoryService.forget(int(parts[1])))
    if result["success"]:
        write(f"Esqueci: {result['data'].content}")
    else:
        write("Não existe nenhuma memória com esse número.")


def _show_mcp_tools(write: Callable[[str], None], context: ToolContext) -> None:
    if not context.session_tools:
        write(f"Não há ferramentas MCP ligadas. Adiciona servidores com 'ayan mcp add' ({MCP_CONFIG_PATH}).")
        return
    write("Ferramentas MCP ligadas:")
    for tool in context.session_tools:
        status = "aprovada nesta sessão" if tool.definition.name in context.approved_tools else "pede aprovação"
        write(f"  {tool.definition.name} ({status})")


def _prompt_api_key(has_current: bool) -> str | None:
    hint = " (Enter para manter a atual)" if has_current else ""
    while True:
        api_key = getpass.getpass(f"Chave API da OpenAI{hint}: ").strip()
        if api_key or has_current:
            return api_key or None
        print("A chave não pode estar vazia.")


def _prompt_model_name(current: str | None) -> str:
    hint = f" [{current}]" if current else ""
    while True:
        model = input(f"Nome do modelo da OpenAI a usar{hint}: ").strip() or current
        if model:
            return model
        print("Indica o nome de um modelo disponível na tua conta OpenAI.")


def choose_model(
    models: list[str],
    current: str | None,
    read_line: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> str:
    write("\nModelos disponíveis na tua conta:")
    for number, model in enumerate(models, start=1):
        marker = "  (atual)" if model == current else ""
        write(f"  {number:>2}) {model}{marker}")

    default = current if current in models else None
    hint = f" [Enter = {default}]" if default else ""
    while True:
        answer = read_line(f"Escolhe o número do modelo{hint}: ").strip()
        if not answer and default:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(models):
            return models[int(answer) - 1]
        write(f"Escreve um número entre 1 e {len(models)}.")


def configure(run: Runner) -> None:
    current_key = user_settings.get_api_key()
    while True:
        new_key = _prompt_api_key(has_current=current_key is not None)
        OpenAIConnect.configure(new_key or current_key)
        result = run(ChatService.available_models())
        if result["success"] or result["error"] != "llm_auth_failed":
            break
        print("A OpenAI rejeitou esta chave. Confirma-a e tenta novamente.")
        current_key = None

    if new_key:
        user_settings.save_api_key(new_key)

    current_model = user_settings.get_model()
    if result["success"] and result["data"]:
        model = choose_model(result["data"], current_model)
    else:
        print(_error_text(result) if not result["success"] else "A conta não tem modelos de chat disponíveis.")
        model = _prompt_model_name(current_model)
    user_settings.save_model(model)
    print(f"Configuração guardada: modelo {model}. A chave fica no Gestor de Credenciais do Windows.")
    if user_settings.api_key_comes_from_env():
        print("Atenção: a variável OPENAI_API_KEY está definida e tem prioridade sobre a chave guardada.")
    configure_tmdb(run)
    configure_lastfm(run)


def configure_tmdb(
    run: Runner,
    read_secret: Callable[[str], str] = getpass.getpass,
    write: Callable[[str], None] = print,
) -> None:
    hint = "Enter para manter a atual" if user_settings.get_tmdb_api_key() else "Enter para saltar"
    write(
        "\nTMDB (opcional): permite ao agente pesquisar filmes e séries. "
        "A chave está em https://www.themoviedb.org/settings/api"
    )
    while True:
        api_key = read_secret(f"Chave API do TMDB ({hint}): ").strip()
        if not api_key:
            return
        result = run(TmdbCredentialsService.validate_key(api_key))
        if result["success"]:
            user_settings.save_tmdb_api_key(result["data"])
            write("Chave do TMDB validada e guardada no Gestor de Credenciais do Windows.")
            return
        if result["error"] != "invalid_key":
            write(f"Não foi possível contactar o TMDB para validar a chave ({result.get('detail')}). "
                  "Tenta mais tarde com 'ayan config'.")
            return
        write("O TMDB rejeitou esta chave. Confirma-a e tenta novamente.")


def configure_lastfm(
    run: Runner,
    read_secret: Callable[[str], str] = getpass.getpass,
    write: Callable[[str], None] = print,
) -> None:
    hint = "Enter para manter a atual" if user_settings.get_lastfm_api_key() else "Enter para saltar"
    write(
        "\nLast.fm (opcional): permite ao agente consultar informação sobre artistas e álbuns. "
        "A chave está em https://www.last.fm/api/account/create"
    )
    while True:
        api_key = read_secret(f"Chave API do Last.fm ({hint}): ").strip()
        if not api_key:
            return
        result = run(LastFmCredentialsService.validate_key(api_key))
        if result["success"]:
            user_settings.save_lastfm_api_key(result["data"])
            write("Chave do Last.fm validada e guardada no Gestor de Credenciais do Windows.")
            return
        if result["error"] != "invalid_key":
            write(f"Não foi possível contactar o Last.fm para validar a chave ({result.get('detail')}). "
                  "Tenta mais tarde com 'ayan config'.")
            return
        write("O Last.fm rejeitou esta chave. Confirma-a e tenta novamente.")


def logout() -> None:
    if user_settings.delete_api_key():
        print("Chave API apagada deste computador.")
    else:
        print("Não havia nenhuma chave API guardada.")


def _start_chat(run: Runner) -> None:
    if not user_settings.get_api_key() or not user_settings.get_model():
        print("Primeira utilização: configura a tua chave da OpenAI.")
        configure(run)
    OpenAIConnect.configure(user_settings.get_api_key(), user_settings.get_model())
    workspace = Path.cwd()
    approved_folders = initial_approved_folders(workspace)
    if not approved_folders:
        print(
            f"Aviso: {workspace} é uma pasta demasiado ampla. Vou pedir-te autorização antes de ler "
            "qualquer pasta. Para trabalhar sem tantas perguntas, abre o ayan na pasta do teu projeto."
        )

    connection = run(McpToolsService.connect())["data"]
    for warning in connection.warnings:
        print(f"Aviso: {warning}")
    if connection.servers:
        listed = ", ".join(f"{name} ({count} ferramentas)" for name, count in connection.servers.items())
        print(f"Servidores MCP ligados: {listed}")

    context = ToolContext(workspace, confirm_action, approved_folders, session_tools=tuple(connection.tools))
    try:
        run_chat(input, print, run, context)
    finally:
        run(McpToolsService.disconnect())


def _manage_mcp(args: argparse.Namespace) -> int:
    try:
        if args.mcp_command == "list":
            servers, warnings = mcp_settings.load_server_configs()
            for warning in warnings:
                print(f"Aviso: {warning}")
            if not servers:
                print(f"Não há servidores MCP configurados ({MCP_CONFIG_PATH}).")
            for server in servers:
                cwd = f"  (pasta: {server.cwd})" if server.cwd else ""
                print(f"  {server.name}: {server.command} {' '.join(server.args)}{cwd}")
        elif args.mcp_command == "add":
            try:
                server = McpServerConfig(
                    name=args.name, command=args.server_command, args=args.server_args, cwd=args.cwd
                )
            except ValidationError:
                print("Nome inválido: usa só letras, números, '-' e '_' (máximo 30 caracteres).")
                return 1
            mcp_settings.add_server(server)
            print(f"Servidor MCP '{server.name}' guardado em {MCP_CONFIG_PATH}. Fica disponível no próximo 'ayan'.")
        elif args.mcp_command == "remove":
            if mcp_settings.remove_server(args.name):
                print(f"Servidor MCP '{args.name}' removido.")
            else:
                print(f"Não existe nenhum servidor MCP chamado '{args.name}'.")
    except mcp_settings.McpConfigError as exc:
        print(f"Erro: {exc}")
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ayan",
        description="Chat com a OpenAI no terminal, usando a tua própria chave API.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("chat", help="iniciar uma conversa (comando por defeito)")
    commands.add_parser("config", help="definir a chave API e o modelo")
    commands.add_parser("logout", help="apagar a chave API guardada neste computador")

    mcp = commands.add_parser("mcp", help="gerir os servidores MCP que o agente pode usar")
    mcp_commands = mcp.add_subparsers(dest="mcp_command", required=True)
    mcp_commands.add_parser("list", help="listar os servidores MCP configurados")
    add = mcp_commands.add_parser(
        "add",
        help="adicionar um servidor MCP (stdio)",
        description="Exemplo: ayan mcp add tmdb --cwd C:\\caminho\\tmdb-mcp C:\\caminho\\tmdb-mcp\\.venv\\Scripts\\python.exe -m tmdb_mcp",
    )
    add.add_argument("name", help="nome curto do servidor (letras, números, '-' e '_')")
    add.add_argument("--cwd", help="pasta onde o servidor corre")
    add.add_argument("server_command", help="comando que arranca o servidor")
    add.add_argument("server_args", nargs=argparse.REMAINDER, help="argumentos do comando")
    remove = mcp_commands.add_parser("remove", help="remover um servidor MCP")
    remove.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    configure_logging("ERROR")
    try:
        if args.command == "logout":
            logout()
            return 0
        if args.command == "mcp":
            return _manage_mcp(args)
        with asyncio.Runner() as runner:
            if args.command == "config":
                configure(runner.run)
            else:
                _start_chat(runner.run)
    except (KeyboardInterrupt, EOFError):
        print()
    return 0
