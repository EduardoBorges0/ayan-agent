from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMUnavailableError
from data.model.chat_model import ChatMessage
from service.chat_service import ChatService

USER_MESSAGES = [ChatMessage(role="user", content="Olá")]


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_model_text_on_success(mock_gateway):
    mock_gateway.generate_reply = AsyncMock(return_value="Olá! Em que posso ajudar?")

    result = await ChatService.reply(USER_MESSAGES)

    assert result["success"] is True
    assert result["data"].reply == "Olá! Em que posso ajudar?"


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_rejects_conversation_not_ending_with_user_message(mock_gateway):
    mock_gateway.generate_reply = AsyncMock()
    messages = USER_MESSAGES + [ChatMessage(role="assistant", content="Olá!")]

    result = await ChatService.reply(messages)

    assert result == {"success": False, "error": "last_message_not_from_user"}
    mock_gateway.generate_reply.assert_not_called()


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_llm_unavailable_when_gateway_fails(mock_gateway):
    mock_gateway.generate_reply = AsyncMock(side_effect=LLMUnavailableError())

    result = await ChatService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "llm_unavailable"}


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_empty_reply_when_model_returns_blank_text(mock_gateway):
    mock_gateway.generate_reply = AsyncMock(return_value="   ")

    result = await ChatService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "empty_reply"}
