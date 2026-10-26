from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

from data.gateway.openai_gateway import LLMUnavailableError, OpenAIGateway
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
