from unittest.mock import AsyncMock, patch

import pytest

from data.model.memory_model import Memory
from service.memory_service import KEEP_RECENT_MEMORIES, MAX_MEMORY_LENGTH, MEMORY_CHAR_LIMIT, MemoryService


def _memory(memory_id: int, content: str) -> Memory:
    return Memory(id=memory_id, content=content, created_at="2026-10-26 10:00:00")


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_remember_saves_normalized_content(mock_gateway):
    mock_gateway.list_all.return_value = []
    mock_gateway.get_summary.return_value = None
    mock_gateway.add.return_value = _memory(1, "Prefere respostas curtas.")

    result = await MemoryService.remember("  Prefere   respostas curtas.  ")

    assert result["success"] is True
    mock_gateway.add.assert_called_once_with("Prefere respostas curtas.")


@pytest.mark.asyncio
@pytest.mark.parametrize("content, error", [
    ("   ", "empty_memory"),
    ("x" * 301, "memory_too_long"),
    ("A chave dele é sk-proj-abcdefghijklmnopqrstuvwxyz", "memory_looks_like_secret"),
])
@patch("service.memory_service.MemoryGateway")
async def test_remember_rejects_invalid_content_without_saving(mock_gateway, content, error):
    mock_gateway.list_all.return_value = []

    result = await MemoryService.remember(content)

    assert result == {"success": False, "error": error}
    mock_gateway.add.assert_not_called()


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_remember_rejects_duplicate_ignoring_case(mock_gateway):
    mock_gateway.list_all.return_value = [_memory(1, "Prefere respostas curtas.")]

    result = await MemoryService.remember("prefere respostas CURTAS.")

    assert result == {"success": False, "error": "memory_already_exists"}
    mock_gateway.add.assert_not_called()


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_forget_returns_not_found_for_unknown_id(mock_gateway):
    mock_gateway.get_by_id.return_value = None

    result = await MemoryService.forget(42)

    assert result == {"success": False, "error": "memory_not_found"}
    mock_gateway.delete.assert_not_called()


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_forget_deletes_and_returns_forgotten_memory(mock_gateway):
    mock_gateway.get_by_id.return_value = _memory(3, "Gosta de tópicos.")

    result = await MemoryService.forget(3)

    assert result["data"].content == "Gosta de tópicos."
    mock_gateway.delete.assert_called_once_with(3)


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_get_summary_returns_stored_summary(mock_gateway):
    mock_gateway.get_summary.return_value = "Trabalha em TI."

    result = await MemoryService.get_summary()

    assert result == {"success": True, "data": "Trabalha em TI."}


def _full_memories(count: int) -> list[Memory]:
    return [_memory(i, f"{i}:" + "x" * (MAX_MEMORY_LENGTH - 5)) for i in range(1, count + 1)]


@pytest.mark.asyncio
@patch("service.memory_service.SummaryService")
@patch("service.memory_service.MemoryGateway")
async def test_remember_does_not_summarize_while_under_the_character_limit(mock_gateway, mock_summary):
    mock_summary.summarize = AsyncMock()
    mock_gateway.list_all.return_value = []
    mock_gateway.get_summary.return_value = "Resumo curto."
    mock_gateway.add.return_value = _memory(1, "Prefere tópicos.")

    result = await MemoryService.remember("Prefere tópicos.")

    assert result["success"] is True
    mock_summary.summarize.assert_not_called()
    mock_gateway.compact.assert_not_called()


@pytest.mark.asyncio
@patch("service.memory_service.SummaryService")
@patch("service.memory_service.MemoryGateway")
async def test_remember_summarizes_older_memories_and_keeps_the_most_recent(mock_gateway, mock_summary):
    existing = _full_memories(MEMORY_CHAR_LIMIT // MAX_MEMORY_LENGTH + 3)
    new = _memory(len(existing) + 1, "Nova memória.")
    mock_gateway.list_all.return_value = existing
    mock_gateway.get_summary.return_value = "Resumo antigo."
    mock_gateway.add.return_value = new
    mock_summary.summarize = AsyncMock(return_value={"success": True, "data": "Resumo novo."})

    result = await MemoryService.remember("Nova memória.")

    assert result["data"] is new
    everything = [*existing, new]
    summarized = everything[:-KEEP_RECENT_MEMORIES]
    mock_gateway.compact.assert_called_once_with("Resumo novo.", summarized[-1].id)
    text = mock_summary.summarize.call_args.args[1]
    assert "Resumo antigo." in text
    assert summarized[0].content in text
    assert everything[-1].content not in text


@pytest.mark.asyncio
@patch("service.memory_service.SummaryService")
@patch("service.memory_service.MemoryGateway")
async def test_failed_summary_keeps_all_memories_and_still_reports_success(mock_gateway, mock_summary):
    existing = _full_memories(MEMORY_CHAR_LIMIT // MAX_MEMORY_LENGTH + 3)
    mock_gateway.list_all.return_value = existing
    mock_gateway.get_summary.return_value = None
    mock_gateway.add.return_value = _memory(len(existing) + 1, "Nova memória.")
    mock_summary.summarize = AsyncMock(return_value={"success": False, "error": "llm_unavailable"})

    result = await MemoryService.remember("Nova memória.")

    assert result["success"] is True
    mock_gateway.compact.assert_not_called()


@pytest.mark.asyncio
@patch("service.memory_service.SummaryService")
@patch("service.memory_service.MemoryGateway")
async def test_nothing_is_summarized_when_only_recent_memories_exist(mock_gateway, mock_summary):
    mock_summary.summarize = AsyncMock()
    mock_gateway.list_all.return_value = []
    mock_gateway.get_summary.return_value = "x" * (MEMORY_CHAR_LIMIT + 1)
    mock_gateway.add.return_value = _memory(1, "Nova memória.")

    await MemoryService.remember("Nova memória.")

    mock_summary.summarize.assert_not_called()
