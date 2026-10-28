from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from data.model.agent_model import ToolContext
from service.agent.personality_tools import PERSONALITY_TOOLS, UPDATE_PERSONALITY_TOOL_NAME

CONTEXT = ToolContext(workspace=Path("."), confirm=lambda _: False)
TOOLS = {tool.definition.name: tool for tool in PERSONALITY_TOOLS}


@pytest.mark.asyncio
@patch("service.agent.personality_tools.PersonalityService")
async def test_update_personality_saves_and_reports_event(mock_personality):
    mock_personality.update_personality = AsyncMock(return_value={"success": True, "data": "Fazes piadas."})

    outcome = await TOOLS[UPDATE_PERSONALITY_TOOL_NAME].run('{"content": "Fazes piadas."}', CONTEXT)

    assert outcome.output.startswith("Personalidade atualizada.")
    assert outcome.event == "Atualizei a minha personalidade (vê-a com /personalidade)."
    mock_personality.update_personality.assert_awaited_once_with("Fazes piadas.")


@pytest.mark.asyncio
@pytest.mark.parametrize("error, explanation", [
    ("empty_personality", "Erro: a personalidade está vazia."),
    ("personality_too_long", "Erro: a personalidade tem mais de"),
    ("personality_not_saved", "Erro: não foi possível gravar"),
])
@patch("service.agent.personality_tools.PersonalityService")
async def test_rejected_personality_is_explained_to_model_without_event(mock_personality, error, explanation):
    mock_personality.update_personality = AsyncMock(return_value={"success": False, "error": error})

    outcome = await TOOLS[UPDATE_PERSONALITY_TOOL_NAME].run('{"content": "x"}', CONTEXT)

    assert outcome.output.startswith(explanation)
    assert outcome.event is None
