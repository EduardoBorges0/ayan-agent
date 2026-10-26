from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMUnavailableError
from data.model.agent_model import ModelTurn, ToolCall
from data.model.chat_model import ChatMessage
from data.model.memory_model import Memory
from service.agent_service import MAX_TOOL_ROUNDS, AgentService

USER_MESSAGES = [ChatMessage(role="user", content="A partir de agora responde em tópicos.")]


def _memory(memory_id: int, content: str) -> Memory:
    return Memory(id=memory_id, content=content, created_at="2026-10-26 10:00:00")


def _memories(*memories: Memory) -> AsyncMock:
    return AsyncMock(return_value={"success": True, "data": list(memories)})


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_existing_memories_are_included_in_instructions(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories(_memory(7, "Trabalha na Almovi."))
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES)

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert "[7] Trabalha na Almovi." in instructions


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_save_memory_tool_call_saves_and_reports_event(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories()
    mock_memory.remember = AsyncMock(
        return_value={"success": True, "data": _memory(1, "Prefere respostas em tópicos.")}
    )
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "save_memory", '{"content": "Prefere respostas em tópicos."}')]),
        ModelTurn(text="Combinado."),
    ])

    result = await AgentService.reply(USER_MESSAGES)

    assert result["success"] is True
    assert result["data"].reply == "Combinado."
    assert result["data"].memory_events == ["Guardei na memória: Prefere respostas em tópicos."]
    mock_memory.remember.assert_awaited_once_with("Prefere respostas em tópicos.")
    tool_rounds = mock_gateway.generate_turn.call_args_list[1].args[3]
    assert tool_rounds[0].results[0].output == "Memória guardada com o número 1."


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_forget_memory_tool_call_deletes_and_reports_event(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories(_memory(2, "Mora em Lisboa."))
    mock_memory.forget = AsyncMock(return_value={"success": True, "data": _memory(2, "Mora em Lisboa.")})
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "forget_memory", '{"memory_id": 2}')]),
        ModelTurn(text="Já esqueci."),
    ])

    result = await AgentService.reply(USER_MESSAGES)

    assert result["data"].memory_events == ["Esqueci: Mora em Lisboa."]
    mock_memory.forget.assert_awaited_once_with(2)


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_rejected_memory_is_reported_to_model_without_event(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories()
    mock_memory.remember = AsyncMock(return_value={"success": False, "error": "memory_looks_like_secret"})
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "save_memory", '{"content": "sk-..."}')]),
        ModelTurn(text="Não guardo chaves."),
    ])

    result = await AgentService.reply(USER_MESSAGES)

    assert result["data"].memory_events == []
    output = mock_gateway.generate_turn.call_args_list[1].args[3][0].results[0].output
    assert output.startswith("Erro: parece conter uma chave")


@pytest.mark.asyncio
@pytest.mark.parametrize("call, expected_output", [
    (ToolCall("c1", "save_memory", "isto não é json"), "Erro: argumentos inválidos."),
    (ToolCall("c1", "forget_memory", '{"memory_id": "dois"}'), "Erro: argumentos inválidos."),
    (ToolCall("c1", "delete_files", "{}"), "Erro: ferramenta desconhecida."),
])
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_bad_tool_calls_return_error_to_model(mock_gateway, mock_memory, call, expected_output):
    mock_memory.list_memories = _memories()
    mock_gateway.generate_turn = AsyncMock(side_effect=[ModelTurn(text="", tool_calls=[call]), ModelTurn(text="Ok.")])

    result = await AgentService.reply(USER_MESSAGES)

    assert result["success"] is True
    output = mock_gateway.generate_turn.call_args_list[1].args[3][0].results[0].output
    assert output == expected_output


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_tools_are_disabled_on_the_last_round(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories()
    mock_memory.remember = AsyncMock(return_value={"success": False, "error": "memory_already_exists"})
    looping_turn = ModelTurn(text="", tool_calls=[ToolCall("c1", "save_memory", '{"content": "x"}')])
    mock_gateway.generate_turn = AsyncMock(side_effect=[looping_turn] * MAX_TOOL_ROUNDS + [ModelTurn(text="Fim.")])

    result = await AgentService.reply(USER_MESSAGES)

    assert result["data"].reply == "Fim."
    allow_tools = [call.kwargs["allow_tools"] for call in mock_gateway.generate_turn.call_args_list]
    assert allow_tools == [True] * MAX_TOOL_ROUNDS + [False]


@pytest.mark.asyncio
@patch("service.agent_service.MemoryService")
@patch("service.agent_service.OpenAIGateway")
async def test_llm_failure_returns_reason(mock_gateway, mock_memory):
    mock_memory.list_memories = _memories()
    mock_gateway.generate_turn = AsyncMock(side_effect=LLMUnavailableError("HTTP 404: modelo sem acesso"))

    result = await AgentService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "llm_unavailable", "detail": "HTTP 404: modelo sem acesso"}
