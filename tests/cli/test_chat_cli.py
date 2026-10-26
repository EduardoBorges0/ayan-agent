import asyncio
from unittest.mock import AsyncMock, patch

from cli.chat_cli import run_chat
from data.model.chat_model import ChatResponse


def _scripted_input(*lines: str):
    remaining = list(lines)

    def read_line(_prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read_line


def _ok(reply: str) -> dict:
    return {"success": True, "data": ChatResponse(reply=reply)}


@patch("cli.chat_cli.ChatService")
def test_second_message_is_sent_with_previous_turns_as_history(mock_service):
    mock_service.reply = AsyncMock(side_effect=[_ok("Olá!"), _ok("Das 9h às 18h.")])
    output: list[str] = []

    run_chat(_scripted_input("Olá", "Qual é o horário?", "/sair"), output.append, asyncio.run)

    sent = mock_service.reply.call_args_list[1].args[0]
    assert [(m.role, m.content) for m in sent] == [
        ("user", "Olá"),
        ("assistant", "Olá!"),
        ("user", "Qual é o horário?"),
    ]
    assert "\nAyan: Das 9h às 18h." in output


@patch("cli.chat_cli.ChatService")
def test_rejected_api_key_shows_config_hint_and_drops_failed_message(mock_service):
    mock_service.reply = AsyncMock(
        side_effect=[{"success": False, "error": "llm_auth_failed"}, _ok("Olá!")]
    )
    output: list[str] = []

    run_chat(_scripted_input("Primeira", "Segunda"), output.append, asyncio.run)

    assert any("ayan config" in line for line in output)
    sent = mock_service.reply.call_args_list[1].args[0]
    assert [m.content for m in sent] == ["Segunda"]


@patch("cli.chat_cli.ChatService")
def test_openai_failure_shows_reason_given_by_openai(mock_service):
    mock_service.reply = AsyncMock(return_value={
        "success": False, "error": "llm_unavailable", "detail": "HTTP 429: You exceeded your current quota.",
    })
    output: list[str] = []

    run_chat(_scripted_input("Olá"), output.append, asyncio.run)

    assert any("HTTP 429: You exceeded your current quota." in line for line in output)


@patch("cli.chat_cli.ChatService")
def test_clear_command_starts_a_new_conversation(mock_service):
    mock_service.reply = AsyncMock(side_effect=[_ok("Olá!"), _ok("Nova conversa.")])

    run_chat(_scripted_input("Olá", "/limpar", "Outra coisa"), lambda _: None, asyncio.run)

    sent = mock_service.reply.call_args_list[1].args[0]
    assert [m.content for m in sent] == ["Outra coisa"]


@patch("cli.chat_cli.ChatService")
def test_too_long_message_is_not_sent(mock_service):
    mock_service.reply = AsyncMock()
    output: list[str] = []

    run_chat(_scripted_input("x" * 8001), output.append, asyncio.run)

    mock_service.reply.assert_not_called()
    assert any("demasiado longa" in line for line in output)
