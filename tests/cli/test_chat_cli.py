import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cli.chat_cli import confirm_action, run_chat
from data.model.agent_model import AgentReply, ToolContext
from data.model.memory_model import Memory

CONTEXT = ToolContext(workspace=Path("."), confirm=lambda _: False)


def _scripted_input(*lines: str):
    remaining = list(lines)

    def read_line(_prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return read_line


def _ok(reply: str) -> dict:
    return {"success": True, "data": AgentReply(reply=reply)}


def test_confirm_action_shows_action_and_accepts_only_explicit_yes():
    output: list[str] = []

    assert confirm_action("executar no PowerShell:\n    Get-Date", lambda _: "s", output.append) is True
    assert confirm_action("executar", lambda _: "Sim", lambda _: None) is True
    assert confirm_action("executar", lambda _: "", lambda _: None) is False
    assert confirm_action("executar", lambda _: "talvez", lambda _: None) is False
    assert "Get-Date" in output[0]


@patch("cli.chat_cli.AgentService")
def test_tool_context_is_passed_to_agent(mock_service):
    mock_service.reply = AsyncMock(return_value=_ok("Olá!"))

    run_chat(_scripted_input("Olá"), lambda _: None, asyncio.run, CONTEXT)

    assert mock_service.reply.call_args.args[1] is CONTEXT


@patch("cli.chat_cli.AgentService")
def test_second_message_is_sent_with_previous_turns_as_history(mock_service):
    mock_service.reply = AsyncMock(side_effect=[_ok("Olá!"), _ok("Das 9h às 18h.")])
    output: list[str] = []

    run_chat(_scripted_input("Olá", "Qual é o horário?", "/sair"), output.append, asyncio.run, CONTEXT)

    sent = mock_service.reply.call_args_list[1].args[0]
    assert [(m.role, m.content) for m in sent] == [
        ("user", "Olá"),
        ("assistant", "Olá!"),
        ("user", "Qual é o horário?"),
    ]
    assert "\nAyan: Das 9h às 18h." in output


@patch("cli.chat_cli.AgentService")
def test_rejected_api_key_shows_config_hint_and_drops_failed_message(mock_service):
    mock_service.reply = AsyncMock(
        side_effect=[{"success": False, "error": "llm_auth_failed"}, _ok("Olá!")]
    )
    output: list[str] = []

    run_chat(_scripted_input("Primeira", "Segunda"), output.append, asyncio.run, CONTEXT)

    assert any("ayan config" in line for line in output)
    sent = mock_service.reply.call_args_list[1].args[0]
    assert [m.content for m in sent] == ["Segunda"]


@patch("cli.chat_cli.AgentService")
def test_openai_failure_shows_reason_given_by_openai(mock_service):
    mock_service.reply = AsyncMock(return_value={
        "success": False, "error": "llm_unavailable", "detail": "HTTP 429: You exceeded your current quota.",
    })
    output: list[str] = []

    run_chat(_scripted_input("Olá"), output.append, asyncio.run, CONTEXT)

    assert any("HTTP 429: You exceeded your current quota." in line for line in output)


@patch("cli.chat_cli.AgentService")
def test_clear_command_starts_a_new_conversation(mock_service):
    mock_service.reply = AsyncMock(side_effect=[_ok("Olá!"), _ok("Nova conversa.")])

    run_chat(_scripted_input("Olá", "/limpar", "Outra coisa"), lambda _: None, asyncio.run, CONTEXT)

    sent = mock_service.reply.call_args_list[1].args[0]
    assert [m.content for m in sent] == ["Outra coisa"]


@patch("cli.chat_cli.AgentService")
def test_memory_events_are_shown_before_reply(mock_service):
    mock_service.reply = AsyncMock(return_value={
        "success": True,
        "data": AgentReply(reply="Combinado.", events=["Guardei na memória: Prefere tópicos."]),
    })
    output: list[str] = []

    run_chat(_scripted_input("Responde sempre em tópicos"), output.append, asyncio.run, CONTEXT)

    event_index = output.index("  · Guardei na memória: Prefere tópicos.")
    assert output.index("\nAyan: Combinado.") > event_index


@patch("cli.chat_cli.MemoryService")
@patch("cli.chat_cli.AgentService")
def test_memory_command_lists_memories_without_calling_the_model(mock_agent, mock_memory):
    mock_agent.reply = AsyncMock()
    mock_memory.list_memories = AsyncMock(return_value={
        "success": True, "data": [Memory(id=4, content="Trabalha na Almovi.", created_at="2026-10-26")],
    })
    output: list[str] = []

    run_chat(_scripted_input("/memoria"), output.append, asyncio.run, CONTEXT)

    assert "    4) Trabalha na Almovi." in output
    mock_agent.reply.assert_not_called()


@patch("cli.chat_cli.MemoryService")
@patch("cli.chat_cli.AgentService")
def test_forget_command_deletes_memory_by_number(mock_agent, mock_memory):
    mock_memory.forget = AsyncMock(return_value={
        "success": True, "data": Memory(id=4, content="Trabalha na Almovi.", created_at="2026-10-26"),
    })
    output: list[str] = []

    run_chat(_scripted_input("/esquecer 4", "/esquecer abc"), output.append, asyncio.run, CONTEXT)

    mock_memory.forget.assert_awaited_once_with(4)
    assert "Esqueci: Trabalha na Almovi." in output
    assert any(line.startswith("Usa: /esquecer N") for line in output)


@patch("cli.chat_cli.MemoryService")
@patch("cli.chat_cli.AgentService")
def test_command_is_recognized_even_with_byte_order_mark_from_piped_input(mock_agent, mock_memory):
    mock_agent.reply = AsyncMock()
    mock_memory.list_memories = AsyncMock(return_value={"success": True, "data": []})

    run_chat(_scripted_input("﻿/memoria"), lambda _: None, asyncio.run, CONTEXT)

    mock_agent.reply.assert_not_called()
    mock_memory.list_memories.assert_awaited_once()


@patch("cli.chat_cli.AgentService")
def test_too_long_message_is_not_sent(mock_service):
    mock_service.reply = AsyncMock()
    output: list[str] = []

    run_chat(_scripted_input("x" * 8001), output.append, asyncio.run, CONTEXT)

    mock_service.reply.assert_not_called()
    assert any("demasiado longa" in line for line in output)
