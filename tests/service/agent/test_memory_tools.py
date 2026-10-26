from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from data.model.agent_model import ToolContext
from data.model.memory_model import Memory
from service.agent.memory_tools import MEMORY_TOOLS

CONTEXT = ToolContext(workspace=Path("."), confirm=lambda _: False)
TOOLS = {tool.definition.name: tool for tool in MEMORY_TOOLS}


def _memory(memory_id: int, content: str) -> Memory:
    return Memory(id=memory_id, content=content, created_at="2026-10-26 10:00:00")


@pytest.mark.asyncio
@patch("service.agent.memory_tools.MemoryService")
async def test_save_memory_saves_and_reports_event(mock_memory):
    mock_memory.remember = AsyncMock(return_value={"success": True, "data": _memory(1, "Prefere tópicos.")})

    outcome = await TOOLS["save_memory"].run('{"content": "Prefere tópicos."}', CONTEXT)

    assert outcome.output == "Memória guardada com o número 1."
    assert outcome.event == "Guardei na memória: Prefere tópicos."
    mock_memory.remember.assert_awaited_once_with("Prefere tópicos.")


@pytest.mark.asyncio
@patch("service.agent.memory_tools.MemoryService")
async def test_rejected_memory_is_explained_to_model_without_event(mock_memory):
    mock_memory.remember = AsyncMock(return_value={"success": False, "error": "memory_looks_like_secret"})

    outcome = await TOOLS["save_memory"].run('{"content": "sk-..."}', CONTEXT)

    assert outcome.output.startswith("Erro: parece conter uma chave")
    assert outcome.event is None


@pytest.mark.asyncio
@patch("service.agent.memory_tools.MemoryService")
async def test_forget_memory_deletes_and_reports_event(mock_memory):
    mock_memory.forget = AsyncMock(return_value={"success": True, "data": _memory(2, "Mora em Lisboa.")})

    outcome = await TOOLS["forget_memory"].run('{"memory_id": 2}', CONTEXT)

    assert outcome.event == "Esqueci: Mora em Lisboa."
    mock_memory.forget.assert_awaited_once_with(2)
