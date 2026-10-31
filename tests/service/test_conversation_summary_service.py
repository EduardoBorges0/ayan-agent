from unittest.mock import AsyncMock, patch

import pytest

from data.model.chat_model import ChatMessage
from service.conversation_summary_service import (
    HISTORY_CHAR_LIMIT,
    KEEP_RECENT_MESSAGES,
    ConversationSummaryService,
)


def _history(count: int, size: int) -> list[ChatMessage]:
    return [
        ChatMessage(role="user" if index % 2 == 0 else "assistant", content=f"{index}:" + "x" * size)
        for index in range(count)
    ]


@pytest.mark.asyncio
@patch("service.conversation_summary_service.SummaryService")
async def test_short_history_is_left_untouched_without_calling_the_model(mock_summary):
    mock_summary.summarize = AsyncMock()
    history = _history(6, 100)

    result = await ConversationSummaryService.compact(history, "Resumo antigo.")

    assert result["success"] is True
    assert result["data"].messages == history
    assert result["data"].summary == "Resumo antigo."
    mock_summary.summarize.assert_not_called()


@pytest.mark.asyncio
@patch("service.conversation_summary_service.SummaryService")
async def test_long_history_keeps_recent_messages_and_summarizes_older_ones(mock_summary):
    mock_summary.summarize = AsyncMock(return_value={"success": True, "data": "Resumo novo."})
    history = _history(20, HISTORY_CHAR_LIMIT // 10)

    result = await ConversationSummaryService.compact(history, None)

    assert result["data"].summary == "Resumo novo."
    assert result["data"].messages == history[-KEEP_RECENT_MESSAGES:]
    text = mock_summary.summarize.call_args.args[1]
    assert "0:" in text and "9:" in text
    assert "10:" not in text.split("Mensagens a juntar ao resumo:")[1]


@pytest.mark.asyncio
@patch("service.conversation_summary_service.SummaryService")
async def test_recent_messages_always_start_with_a_user_message(mock_summary):
    mock_summary.summarize = AsyncMock(return_value={"success": True, "data": "Resumo novo."})
    history = _history(21, HISTORY_CHAR_LIMIT // 10)

    result = await ConversationSummaryService.compact(history, None)

    assert result["data"].messages[0].role == "user"
    assert result["data"].messages[-1] == history[-1]


@pytest.mark.asyncio
@patch("service.conversation_summary_service.SummaryService")
async def test_previous_summary_is_sent_to_the_model_to_be_merged(mock_summary):
    mock_summary.summarize = AsyncMock(return_value={"success": True, "data": "Resumo novo."})

    await ConversationSummaryService.compact(_history(20, HISTORY_CHAR_LIMIT // 10), "Falámos do projeto Ayan.")

    assert "Falámos do projeto Ayan." in mock_summary.summarize.call_args.args[1]


@pytest.mark.asyncio
@patch("service.conversation_summary_service.SummaryService")
async def test_summary_failure_is_reported_and_history_is_not_changed(mock_summary):
    mock_summary.summarize = AsyncMock(return_value={"success": False, "error": "llm_unavailable"})

    result = await ConversationSummaryService.compact(_history(20, HISTORY_CHAR_LIMIT // 10), None)

    assert result == {"success": False, "error": "llm_unavailable"}
