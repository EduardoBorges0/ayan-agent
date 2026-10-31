from unittest.mock import AsyncMock, patch

import pytest

from data.gateway.openai_gateway import LLMAuthenticationError, LLMUnavailableError
from data.model.agent_model import ModelTurn
from service.summary_service import SummaryService


@pytest.mark.asyncio
@patch("service.summary_service.OpenAIGateway")
async def test_summarize_returns_trimmed_summary_and_sends_text_with_instructions(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="  Resumo curto.  "))

    result = await SummaryService.summarize("Resume.", "Texto longo.", 100)

    assert result == {"success": True, "data": "Resumo curto."}
    messages, instructions = mock_gateway.generate_turn.call_args.args
    assert [(m.role, m.content) for m in messages] == [("user", "Texto longo.")]
    assert instructions == "Resume."


@pytest.mark.asyncio
@pytest.mark.parametrize("text, error", [("   ", "empty_summary"), ("x" * 101, "summary_too_long")])
@patch("service.summary_service.OpenAIGateway")
async def test_summarize_rejects_empty_or_oversized_summary(mock_gateway, text, error):
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text=text))

    result = await SummaryService.summarize("Resume.", "Texto.", 100)

    assert result == {"success": False, "error": error}


@pytest.mark.asyncio
@patch("service.summary_service.OpenAIGateway")
async def test_summarize_reports_llm_failures(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(side_effect=[LLMUnavailableError("HTTP 503"), LLMAuthenticationError()])

    unavailable = await SummaryService.summarize("Resume.", "Texto.", 100)
    rejected = await SummaryService.summarize("Resume.", "Texto.", 100)

    assert unavailable == {"success": False, "error": "llm_unavailable", "detail": "HTTP 503"}
    assert rejected == {"success": False, "error": "llm_auth_failed"}


@pytest.mark.asyncio
@patch("service.summary_service.OpenAIGateway")
async def test_summarize_accepts_text_longer_than_a_single_chat_message(mock_gateway):
    mock_gateway.generate_turn = AsyncMock(return_value=ModelTurn(text="Resumo."))

    result = await SummaryService.summarize("Resume.", "x" * 20000, 100)

    assert result["success"] is True
