import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cli.chat_cli import _build_parser, configure_lastfm, configure_tmdb, confirm_action, run_chat
from data.model.agent_model import AgentReply, AgentTool, ToolContext, ToolDefinition
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


def test_mcp_command_lists_session_tools_and_their_approval(monkeypatch):
    tools = tuple(
        AgentTool(ToolDefinition(name=name, description="", parameters={}), AsyncMock())
        for name in ("tmdb__search_movies", "tmdb__get_trending")
    )
    context = ToolContext(workspace=Path("."), confirm=lambda _: False, session_tools=tools,
                          approved_tools={"tmdb__search_movies"})
    output: list[str] = []

    run_chat(_scripted_input("/mcp"), output.append, asyncio.run, context)

    assert "  tmdb__search_movies (aprovada nesta sessão)" in output
    assert "  tmdb__get_trending (pede aprovação)" in output


def test_mcp_add_command_keeps_server_arguments_after_the_command():
    args = _build_parser().parse_args(
        ["mcp", "add", "tmdb", "--cwd", "C:/tmdb-mcp", "C:/tmdb-mcp/.venv/Scripts/python.exe", "-m", "tmdb_mcp"]
    )

    assert (args.name, args.cwd, args.server_command) == ("tmdb", "C:/tmdb-mcp", "C:/tmdb-mcp/.venv/Scripts/python.exe")
    assert args.server_args == ["-m", "tmdb_mcp"]


@patch("cli.chat_cli.TmdbCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_tmdb_step_is_skipped_with_enter(mock_settings, mock_credentials):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock()

    configure_tmdb(asyncio.run, read_secret=lambda _: "", write=lambda _: None)

    mock_credentials.validate_key.assert_not_called()
    mock_settings.save_tmdb_api_key.assert_not_called()


@patch("cli.chat_cli.TmdbCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_tmdb_key_is_saved_only_after_tmdb_accepts_it(mock_settings, mock_credentials):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock(side_effect=[
        {"success": False, "error": "invalid_key"},
        {"success": True, "data": "chave-boa"},
    ])
    output: list[str] = []

    configure_tmdb(asyncio.run, read_secret=_scripted_input("chave-errada", "chave-boa"), write=output.append)

    mock_settings.save_tmdb_api_key.assert_called_once_with("chave-boa")
    assert any("rejeitou" in line for line in output)


@patch("cli.chat_cli.TmdbCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_tmdb_step_gives_up_when_tmdb_cannot_be_reached(mock_settings, mock_credentials):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock(
        return_value={"success": False, "error": "tmdb_unavailable", "detail": "ConnectError"}
    )
    read_secret = MagicMock(return_value="uma-chave")

    configure_tmdb(asyncio.run, read_secret=read_secret, write=lambda _: None)

    read_secret.assert_called_once()
    mock_settings.save_tmdb_api_key.assert_not_called()


@patch("cli.chat_cli.AgentService")
def test_too_long_message_is_not_sent(mock_service):
    mock_service.reply = AsyncMock()
    output: list[str] = []

    run_chat(_scripted_input("x" * 8001), output.append, asyncio.run, CONTEXT)

    mock_service.reply.assert_not_called()
    assert any("demasiado longa" in line for line in output)


@patch("cli.chat_cli.LastFmCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_lastfm_step_is_skipped_with_enter(mock_settings, mock_credentials):
    mock_settings.get_lastfm_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock()

    configure_lastfm(asyncio.run, read_secret=lambda _: "", write=lambda _: None)

    mock_credentials.validate_key.assert_not_called()
    mock_settings.save_lastfm_api_key.assert_not_called()


@patch("cli.chat_cli.LastFmCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_lastfm_key_is_saved_only_after_lastfm_accepts_it(mock_settings, mock_credentials):
    mock_settings.get_lastfm_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock(side_effect=[
        {"success": False, "error": "invalid_key"},
        {"success": True, "data": "chave-boa"},
    ])
    output: list[str] = []

    configure_lastfm(asyncio.run, read_secret=_scripted_input("chave-errada", "chave-boa"), write=output.append)

    mock_settings.save_lastfm_api_key.assert_called_once_with("chave-boa")
    assert any("rejeitou" in line for line in output)


@patch("cli.chat_cli.LastFmCredentialsService")
@patch("cli.chat_cli.user_settings")
def test_lastfm_step_gives_up_when_lastfm_cannot_be_reached(mock_settings, mock_credentials):
    mock_settings.get_lastfm_api_key.return_value = None
    mock_credentials.validate_key = AsyncMock(
        return_value={"success": False, "error": "lastfm_unavailable", "detail": "falha de rede (ConnectError)"}
    )
    read_secret = MagicMock(return_value="uma-chave")

    configure_lastfm(asyncio.run, read_secret=read_secret, write=lambda _: None)

    read_secret.assert_called_once()
    mock_settings.save_lastfm_api_key.assert_not_called()
