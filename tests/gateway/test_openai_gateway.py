from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError, OpenAIGateway
from data.model.chat_model import ChatMessage

MESSAGES = [
    ChatMessage(role="user", content="Olá"),
    ChatMessage(role="assistant", content="Olá! Em que posso ajudar?"),
    ChatMessage(role="user", content="Qual é o horário?"),
]


def _client_returning(**create_kwargs) -> MagicMock:
    client = MagicMock()
    client.responses.create = AsyncMock(**create_kwargs)
    return client


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_reply_sends_history_and_instructions_and_returns_text(mock_connect):
    client = _client_returning(return_value=MagicMock(output_text="Das 9h às 18h."))
    mock_connect.get_client.return_value = client

    reply = await OpenAIGateway.generate_reply(MESSAGES, "instruções de teste")

    assert reply == "Das 9h às 18h."
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["instructions"] == "instruções de teste"
    assert kwargs["input"] == [
        {"role": "user", "content": "Olá"},
        {"role": "assistant", "content": "Olá! Em que posso ajudar?"},
        {"role": "user", "content": "Qual é o horário?"},
    ]
    assert kwargs["store"] is False


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_reply_raises_llm_unavailable_when_sdk_fails(mock_connect):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    mock_connect.get_client.return_value = _client_returning(
        side_effect=openai.APIConnectionError(request=request)
    )

    with pytest.raises(LLMUnavailableError):
        await OpenAIGateway.generate_reply(MESSAGES, "instruções de teste")


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_reply_error_reason_carries_status_and_openai_message(mock_connect):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.RateLimitError(
        "Error code: 429",
        response=httpx.Response(429, request=request),
        body={"message": "You exceeded your current quota.", "code": "insufficient_quota"},
    )
    mock_connect.get_client.return_value = _client_returning(side_effect=error)

    with pytest.raises(LLMUnavailableError) as raised:
        await OpenAIGateway.generate_reply(MESSAGES, "instruções de teste")

    assert raised.value.reason == "HTTP 429: You exceeded your current quota."


@pytest.mark.asyncio
@patch("data.gateway.openai_gateway.OpenAIConnect")
async def test_generate_reply_raises_authentication_error_when_key_is_rejected(mock_connect):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    error = openai.AuthenticationError(
        "Incorrect API key", response=httpx.Response(401, request=request), body=None
    )
    mock_connect.get_client.return_value = _client_returning(side_effect=error)

    with pytest.raises(LLMAuthenticationError):
        await OpenAIGateway.generate_reply(MESSAGES, "instruções de teste")


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
    request = httpx.Request("GET", "https://api.openai.com/v1/models")
    client = MagicMock()
    client.models.list = MagicMock(
        side_effect=openai.AuthenticationError(
            "Incorrect API key", response=httpx.Response(401, request=request), body=None
        )
    )
    mock_connect.get_client.return_value = client

    with pytest.raises(LLMAuthenticationError):
        await OpenAIGateway.list_model_ids()
