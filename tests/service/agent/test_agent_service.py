from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMUnavailableError
from data.model.agent_model import AgentTool, ModelTurn, ToolCall, ToolContext, ToolDefinition, ToolOutcome
from data.model.chat_model import ChatMessage
from data.model.memory_model import Memory
from service.agent.agent_service import MAX_TOOL_ROUNDS, AgentService
from service.personality_service import DEFAULT_PERSONALITY

USER_MESSAGES = [ChatMessage(role="user", content="Que ficheiros há aqui?")]
CONTEXT = ToolContext(
    workspace=Path("C:/projetos/demo"),
    confirm=lambda _: False,
    approved_folders={Path("C:/projetos/demo").resolve()},
)


@pytest.fixture(autouse=True)
def mock_personality():
    with patch("service.agent.agent_service.PersonalityService") as mock_service:
        mock_service.get_personality = AsyncMock(return_value={"success": True, "data": DEFAULT_PERSONALITY})
        yield mock_service


def _no_memories() -> AsyncMock:
    return AsyncMock(return_value={"success": True, "data": []})


def _summary(text: str | None = None) -> AsyncMock:
    return AsyncMock(return_value={"success": True, "data": text})


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_include_memories_and_current_folder(mock_gateway, mock_memory):
    mock_memory.list_memories = AsyncMock(return_value={
        "success": True, "data": [Memory(id=7, content="Trabalha na Almovi.", created_at="2026-10-26")],
    })
    mock_memory.get_summary = _summary()
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
    mock_memory.get_summary = _summary()
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    offered = {tool.name for tool in mock_gateway.generate_turn.call_args.args[2]}
    assert offered == {
        "save_memory", "forget_memory", "update_personality", "read_file", "list_directory", "run_powershell",
    }


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_tool_result_is_sent_back_and_event_is_reported(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
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
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_session_tools_are_offered_and_dispatched(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    session_tool = AgentTool(
        ToolDefinition(name="tmdb__search_movies", description="Pesquisa.", parameters={"type": "object"}),
        AsyncMock(return_value=ToolOutcome("Matrix (1999)", "Usei tmdb.search_movies")),
    )
    context = ToolContext(workspace=CONTEXT.workspace, confirm=lambda _: True, session_tools=(session_tool,))
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "tmdb__search_movies", '{"query": "matrix"}')]),
        ModelTurn(text="Encontrei o Matrix."),
    ])

    result = await AgentService.reply(USER_MESSAGES, context)

    offered = {tool.name for tool in mock_gateway.generate_turn.call_args_list[0].args[2]}
    assert "tmdb__search_movies" in offered
    session_tool.run.assert_awaited_once_with('{"query": "matrix"}', context)
    assert result["data"].events == ["Usei tmdb.search_movies"]


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
    mock_memory.get_summary = _summary()
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
    mock_memory.get_summary = _summary()
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
    mock_memory.get_summary = _summary()
    mock_gateway.generate_turn = AsyncMock(side_effect=LLMUnavailableError("HTTP 404: modelo sem acesso"))

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert result == {"success": False, "error": "llm_unavailable", "detail": "HTTP 404: modelo sem acesso"}


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_include_current_personality(mock_gateway, mock_memory, mock_personality):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    mock_personality.get_personality = AsyncMock(return_value={"success": True, "data": "Fazes piadas sobre os temas."})
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert instructions.endswith("Personalidade atual:\nFazes piadas sobre os temas.")


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_unreadable_personality_falls_back_to_default_and_warns_user(mock_gateway, mock_memory, mock_personality):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    mock_personality.get_personality = AsyncMock(return_value={"success": False, "error": "personality_unreadable"})
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    assert mock_gateway.generate_turn.call_args.args[1].endswith(f"Personalidade atual:\n{DEFAULT_PERSONALITY}")
    assert result["success"] is True
    assert result["data"].events == ["Não consegui ler o ficheiro da personalidade; usei a personalidade padrão."]


@pytest.mark.asyncio
@patch("service.agent.personality_tools.PersonalityService")
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_updated_personality_is_used_in_the_same_reply(mock_gateway, mock_memory, mock_tool_service, mock_personality):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    mock_personality.get_personality = AsyncMock(side_effect=[
        {"success": True, "data": "Antiga."},
        {"success": True, "data": "Fazes piadas sobre os temas."},
    ])
    mock_tool_service.update_personality = AsyncMock(return_value={"success": True, "data": "Fazes piadas sobre os temas."})
    mock_gateway.generate_turn = AsyncMock(side_effect=[
        ModelTurn(text="", tool_calls=[ToolCall("c1", "update_personality", '{"content": "Fazes piadas sobre os temas."}')]),
        ModelTurn(text="Feito, e prometo piadas!"),
    ])

    result = await AgentService.reply(USER_MESSAGES, CONTEXT)

    first_instructions, second_instructions = (call.args[1] for call in mock_gateway.generate_turn.call_args_list)
    assert first_instructions.endswith("Personalidade atual:\nAntiga.")
    assert second_instructions.endswith("Personalidade atual:\nFazes piadas sobre os temas.")
    assert result["data"].events == ["Atualizei a minha personalidade (vê-a com /personalidade)."]


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_include_memory_summary_before_recent_memories(mock_gateway, mock_memory):
    mock_memory.list_memories = AsyncMock(return_value={
        "success": True, "data": [Memory(id=9, content="Gosta de tópicos.", created_at="2026-10-26")],
    })
    mock_memory.get_summary = _summary("Trabalha em TI e prefere respostas curtas.")
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert "Trabalha em TI e prefere respostas curtas." in instructions
    assert instructions.index("Trabalha em TI") < instructions.index("[9] Gosta de tópicos.")


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_include_conversation_summary_when_given(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT, conversation_summary="Falámos do servidor MCP do Last.fm.")

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert "Falámos do servidor MCP do Last.fm." in instructions


@pytest.mark.asyncio
@patch("service.agent.agent_service.MemoryService")
@patch("service.agent.agent_service.OpenAIGateway")
async def test_instructions_have_no_summary_sections_when_there_are_none(mock_gateway, mock_memory):
    mock_memory.list_memories = _no_memories()
    mock_memory.get_summary = _summary()
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá!"))

    await AgentService.reply(USER_MESSAGES, CONTEXT)

    instructions = mock_gateway.generate_turn.call_args.args[1]
    assert "Resumo da memória (memórias antigas" not in instructions
    assert "Resumo da conversa até agora" not in instructions
