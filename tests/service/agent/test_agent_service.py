from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMUnavailableError
from data.model.agent_model import ModelTurn, ToolCall, ToolContext
from data.model.chat_model import ChatMessage
from data.model.memory_model import Memory
from service.agent.agent_service import MAX_TOOL_ROUNDS, AgentService

USER_MESSAGES = [ChatMessage(role="user", content="Que ficheiros há aqui?")]
CONTEXT = ToolContext(
    workspace=Path("C:/projetos/demo"),
    confirm=lambda _: False,
    approved_folders={Path("C:/projetos/demo").resolve()},
)


def _no_memories() -> AsyncMock:
    return AsyncMock(return_value={"success": True, "data": []})


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_include_memories_and_current_folder(mock_gateway, mock_memory):
    mock_memory.list_memories = AsyncMock(return_value={
        "success": True, "data": [Memory(id=7, content="Trabalha na Almovi.", created_at="2026-10-26")],
    })
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert "[7] Trabalha na Almovi." in instructions
    assert f"Pasta atual: {CONTEXT.workspace}" in instructions


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_all_tools_are_offered_to_the_model(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    offered = {tool.name for tool in mock_gateway.generate_turn.call_args.args[2]}
    assert offered == {"save_memory", "forget_memory", "read_file", "list_directory", "run_powershell"}


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_tool_result_is_sent_back_and_event_is_reported(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "list_directory", '{"path": "."}')]),
        ModelTurn(text="Há dois ficheiros."),
    ])

    with patch("service.agent.computer_tools.FilesystemGateway") as mock_fs:
        mock_fs.list_directory.return_value = []
        result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert result["data"].reply == "Há dois ficheiros."
    assert result["data"].events == [f"Listei {CONTEXT.workspace.resolve()}"]
    tool_rounds = mock_gateway.generate_turn.call_args_list[1].args[3]
    assert tool_rounds[0].results[0].output.endswith("(pasta vazia)")


@pytest.mark.asyncio
@pytest.mark.parametrize("call, expected_output", [
    (ToolCall("c1", "read_file", "isto não é json"), "Erro: argumentos inválidos."),
    (ToolCall("c1", "forget_memory", '{"memory_id": "dois"}'), "Erro: argumentos inválidos."),
    (ToolCall("c1", "delete_everything", "{}"), "Erro: ferramenta desconhecida."),
])
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_bad_tool_calls_return_error_to_model(mock_gateway, mock_memory, call, expected_output):
    mock_memory.list_memories = _no_memories()
    mock_gateway.generate_turn = AsyncMock(side_effect=[ModelTurn(text="", tool_calls=[call]), ModelTurn(text="Ok.")])

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert result["success"] is True
    output = mock_gateway.generate_turn.call_args_list[1].args[3][0].results[0].output
    assert output == expected_output


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_tools_are_disabled_on_the_last_round(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    looping_turn = ModelTurn(text="", tool_calls=[ToolCall("c1", "unknown_tool", "{}")])
    mock_gateway.generate_turn = AsyncMock(side_effect=[looping_turn] * MAX_TOOL_ROUNDS + [ModelTurn(text="Fim.")])

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert result["data"].reply == "Fim."
    allow_tools = [call.kwargs["allow_tools"] for call in mock_gateway.generate_turn.call_args_list]
    assert allow_tools == [True] * MAX_TOOL_ROUNDS + [False]


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_llm_failure_returns_reason(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_gateway.generate_turn = AsyncMock(side_effect=LLMUnavailableError("HTTP 404: modelo sem acesso"))

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert result == {"success": False, "error": "llm_unavailable", "detail": "HTTP 404: modelo sem acesso"}
