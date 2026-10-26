from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError
from data.model.agent_model import ModelTurn
from data.model.chat_model import ChatMessage
from service.chat_service import ChatService

USER_MESSAGES = [ChatMessage(role="user", content="Olá")]


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_model_text_on_success(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Olá! Em que posso ajudar?"))

    result = await ChatService.reply(USER_MESSAGES)

    assert result["success"] is True
    assert result["data"].reply == "Olá! Em que posso ajudar?"


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_rejects_conversation_not_ending_with_user_message(mock_gateway):
    mock_gateway.generate_turn = AsyncMock()
    messages = USER_MESSAGES + [ChatMessage(role="assistant", content="Olá!")]

    result = await ChatService.reply(messages)

    assert result == {"success": False, "error": "last_message_not_from_user"}
    mock_gateway.generate_turn.assert_not_called()


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_llm_unavailable_when_gateway_fails(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(side_effect=LLMUnavailableError("HTTP 429: sem quota"))

    result = await ChatService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "llm_unavailable", "detail": "HTTP 429: sem quota"}


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_llm_auth_failed_when_key_is_rejected(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(side_effect=LLMAuthenticationError())

    result = await ChatService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "llm_auth_failed"}


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_available_models_keeps_only_chat_models_sorted(mock_gateway):
    mock_gateway.list_model_ids = AsyncMock(return_value=[
        "gpt-4o-mini", "gpt-4o", "o3", "whisper-1", "text-embedding-3-small", "dall-e-3",
        "gpt-4o-2024-08-06", "gpt-4o-audio-preview", "gpt-4o-realtime-preview", "gpt-4o-mini-tts",
        "gpt-4o-transcribe", "gpt-image-1", "gpt-4o-search-preview", "gpt-3.5-turbo-instruct",
        "omni-moderation-latest", "babbage-002",
    ])

    result = await ChatService.available_models()

    assert result == {"success": True, "data": ["gpt-4o", "gpt-4o-mini", "o3"]}


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_available_models_returns_llm_auth_failed_when_key_is_rejected(mock_gateway):
    mock_gateway.list_model_ids = AsyncMock(side_effect=LLMAuthenticationError())

    result = await ChatService.available_models()

    assert result == {"success": False, "error": "llm_auth_failed"}


@pytest.mark.asyncio
@patch("service.chat_service.OpenAIGateway")
async def test_reply_returns_empty_reply_when_model_returns_blank_text(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="   "))

    result = await ChatService.reply(USER_MESSAGES)

    assert result == {"success": False, "error": "empty_reply"}
