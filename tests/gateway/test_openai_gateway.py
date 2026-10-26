from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError, OpenAIGateway
from data.model.agent_model import ToolCall, ToolDefinition, ToolResult, ToolRound
from data.model.chat_model import ChatMessage

MESSAGES = [
    ChatMessage(role="user", content="Olá"),
    ChatMessage(role="assistant", content="Olá! Em que posso ajudar?"),
    ChatMessage(role="user", content="Prefiro respostas curtas."),
]
TOOL = ToolDefinition(name="save_memory", description="Guarda.", parameters={"type": "object"})


def _completion(content: str | None = None, tool_calls: list | None = None) -> MagicMock:
    message = MagicMock(content=content, tool_calls=tool_calls)
    return MagicMock(choices=[MagicMock(message=message)])


def _function_call(call_id: str, name: str, arguments: str) -> MagicMock:
    call = MagicMock(id=call_id, type="function")
    call.function.name = name
    call.function.arguments = arguments
    return call


def _client(**create_kwargs) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(**create_kwargs)
    return client


def _status_error(error_class, status: int, body: dict | None = None):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return error_class(f"Error code: {status}", response=httpx.Response(status, request=request), body=body)


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_sends_instructions_and_history_and_returns_text(mock_connect):
    client = _client(return_value=_completion(content="Combinado."))
    mock_connect.get_client.return_value = client

    turn = await OpenAIGateway.generate_turn(MESSAGES, "instruções de teste")

    assert turn.text == "Combinado."
    assert turn.tool_calls == []
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"] == [
        {"role": "system", "content": "instruções de teste"},
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Olá! Em que posso ajudar?"},
        {"role": "user", "content": "Prefiro respostas curtas."},
    ]
    assert kwargs["store"] is False
    assert "tools" not in kwargs


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_returns_function_calls_and_ignores_other_tool_types(mock_connect):
    custom_call = MagicMock(type="custom")
    client = _client(return_value=_completion(tool_calls=[
        _function_call("call_1", "save_memory", '{"content": "Prefere respostas curtas."}'),
        custom_call,
    ]))
    mock_connect.get_client.return_value = client

    turn = await OpenAIGateway.generate_turn(MESSAGES, "instruções", tools=[TOOL])

    assert turn.text == ""
    assert turn.tool_calls == [ToolCall("call_1", "save_memory", '{"content": "Prefere respostas curtas."}')]
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["tools"][0]["function"]["name"] == "save_memory"
    assert kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_sends_previous_tool_rounds_and_can_disable_tools(mock_connect):
    client = _client(return_value=_completion(content="Feito."))
    mock_connect.get_client.return_value = client
    tool_round = ToolRound(
        calls=[ToolCall("call_1", "save_memory", '{"content": "x"}')],
        results=[ToolResult("call_1", "Memória guardada com o número 1.")],
    )

    await OpenAIGateway.generate_turn(MESSAGES, "instruções", [TOOL], [tool_round], allow_tools=False)

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["messages"][-2] == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "save_memory", "arguments": '{"content": "x"}'}}
        ],
    }
    assert kwargs["messages"][-1] == {
        "role": "tool", "tool_call_id": "call_1", "content": "Memória guardada com o número 1.",
    }
    assert kwargs["tool_choice"] == "none"


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_raises_llm_unavailable_when_sdk_fails(mock_connect):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    mock_connect.get_client.return_value = _client(side_effect=openai.APIConnectionError(request=request))

    with pytest.raises(LLMUnavailableError):
        await OpenAIGateway.generate_turn(MESSAGES, "instruções")


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_error_reason_carries_status_and_openai_message(mock_connect):
    error = _status_error(openai.NotFoundError, 404, {"message": "The model `o4-mini` does not exist."})
    mock_connect.get_client.return_value = _client(side_effect=error)

    with pytest.raises(LLMUnavailableError) as raised:
        await OpenAIGateway.generate_turn(MESSAGES, "instruções")

    assert raised.value.reason == "HTTP 404: The model `o4-mini` does not exist."


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_turn_raises_authentication_error_when_key_is_rejected(mock_connect):
    mock_connect.get_client.return_value = _client(side_effect=_status_error(openai.AuthenticationError, 401))

    with pytest.raises(LLMAuthenticationError):
        await OpenAIGateway.generate_turn(MESSAGES, "instruções")


def _async_models(*model_ids: str):
    async def iterate():
        for model_id in model_ids:
            yield MagicMock(id=model_id)

    return iterate()


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_list_model_ids_returns_ids_from_account(mock_connect):
    client = MagicMock()
    client.models.list = MagicMock(return_value=_async_models("gpt-4o", "whisper-1"))
    mock_connect.get_client.return_value = client

    assert await OpenAIGateway.list_model_ids() == ["gpt-4o", "whisper-1"]


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_list_model_ids_raises_authentication_error_when_key_is_rejected(mock_connect):
    client = MagicMock()
    client.models.list = MagicMock(side_effect=_status_error(openai.AuthenticationError, 401))
    mock_connect.get_client.return_value = client

    with pytest.raises(LLMAuthenticationError):
        await OpenAIGateway.list_model_ids()
