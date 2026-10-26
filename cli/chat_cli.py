import argparse
import asyncio
import getpass
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError

from config import user_settings
from config.connections.openai_connection import OpenAIConnect
from data.model.chat_model import MAX_HISTORY_MESSAGES, ChatMessage
from service.chat_service import ChatService
from utils.logging_config import configure_logging

EXIT_COMMANDS = {"/sair", "/exit"}
CLEAR_COMMAND = "/limpar"
WELCOME_TEXT = "Escreve a tua mensagem. Comandos: /limpar (nova conversa), /sair (terminar)."

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


def run_chat(read_line: Callable[[str], str], write: Callable[[str], None], run: Runner) -> None:
    history: list[ChatMessage] = []
    write(WELCOME_TEXT)
    while True:
        try:
            text = read_line("\nTu: ").strip()
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

        try:
            history.append(ChatMessage(role="user", content=text))
        except ValidationError:
            write("Mensagem demasiado longa. Divide-a em partes mais pequenas.")
            continue

        result = run(ChatService.reply(history[-MAX_HISTORY_MESSAGES:]))
        if not result["success"]:
            history.pop()
            write(_error_text(result))
            continue

        reply = result["data"].reply
        # O limite de tamanho do ChatMessage protege o input do utilizador, não a resposta do modelo.
        history.append(ChatMessage.model_construct(role="assistant", content=reply))
        write(f"\nAyan: {reply}")


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
    run_chat(input, print, run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ayan",
        description="Chat com a OpenAI no terminal, usando a tua própria chave API.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("chat", help="iniciar uma conversa (comando por defeito)")
    commands.add_parser("config", help="definir a chave API e o modelo")
    commands.add_parser("logout", help="apagar a chave API guardada neste computador")
    args = parser.parse_args(argv)

    configure_logging("ERROR")
    try:
        if args.command == "logout":
            logout()
            return 0
        with asyncio.Runner() as runner:
            if args.command == "config":
                configure(runner.run)
            else:
                _start_chat(runner.run)
    except (KeyboardInterrupt, EOFError):
        print()
    return 0
