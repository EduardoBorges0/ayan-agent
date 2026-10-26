from unittest.mock import patch

import pytest

from data.model.memory_model import Memory
from service.memory_service import MAX_MEMORIES, MemoryService


def _memory(memory_id: int, content: str) -> Memory:
    return Memory(id=memory_id, content=content, created_at="2026-10-26 10:00:00")


@pytest.mark.asyncio
@patch("service.memory_service.MemoryGateway")
async def test_remember_saves_normalized_content(mock_gateway):
    mock_gateway.list_all.return_value = []
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
async def test_remember_rejects_when_memory_is_full(mock_gateway):
    mock_gateway.list_all.return_value = [_memory(i, f"Facto {i}") for i in range(MAX_MEMORIES)]

    result = await MemoryService.remember("Facto novo")

    assert result == {"success": False, "error": "memory_limit_reached"}


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
