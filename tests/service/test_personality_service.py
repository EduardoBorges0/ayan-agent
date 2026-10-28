from unittest.mock import patch

import pytest

from service.personality_service import DEFAULT_PERSONALITY, MAX_PERSONALITY_LENGTH, PersonalityService


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_get_returns_stored_personality(mock_gateway):
    mock_gateway.read.return_value = "Fazes piadas sobre os temas.\n"

    result = await PersonalityService.get_personality()

    assert result == {"success": True, "data": "Fazes piadas sobre os temas."}
    mock_gateway.write.assert_not_called()


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_get_creates_file_with_default_personality_on_first_run(mock_gateway):
    mock_gateway.read.return_value = None

    result = await PersonalityService.get_personality()

    assert result == {"success": True, "data": DEFAULT_PERSONALITY}
    mock_gateway.write.assert_called_once_with(DEFAULT_PERSONALITY)


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_get_still_returns_default_when_file_cannot_be_created(mock_gateway):
    mock_gateway.read.return_value = None
    mock_gateway.write.side_effect = PermissionError("sem permissão")

    result = await PersonalityService.get_personality()

    assert result == {"success": True, "data": DEFAULT_PERSONALITY}


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_get_uses_default_without_overwriting_an_empty_file(mock_gateway):
    mock_gateway.read.return_value = "  \n "

    result = await PersonalityService.get_personality()

    assert result == {"success": True, "data": DEFAULT_PERSONALITY}
    mock_gateway.write.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [PermissionError("sem permissão"), UnicodeDecodeError("utf-8", b"\xe9", 0, 1, "x")])
@patch("service.personality_service.PersonalityGateway")
async def test_get_reports_unreadable_file_without_overwriting_it(mock_gateway, failure):
    mock_gateway.read.side_effect = failure

    result = await PersonalityService.get_personality()

    assert result == {"success": False, "error": "personality_unreadable"}
    mock_gateway.write.assert_not_called()


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_update_saves_trimmed_content_and_keeps_line_breaks(mock_gateway):
    result = await PersonalityService.update_personality("  Fazes piadas.\n\n- Usas humor leve.  \n")

    assert result == {"success": True, "data": "Fazes piadas.\n\n- Usas humor leve."}
    mock_gateway.write.assert_called_once_with("Fazes piadas.\n\n- Usas humor leve.")


@pytest.mark.asyncio
@pytest.mark.parametrize("content, error", [
    ("  \n ", "empty_personality"),
    ("x" * (MAX_PERSONALITY_LENGTH + 1), "personality_too_long"),
])
@patch("service.personality_service.PersonalityGateway")
async def test_update_rejects_invalid_content_without_saving(mock_gateway, content, error):
    result = await PersonalityService.update_personality(content)

    assert result == {"success": False, "error": error}
    mock_gateway.write.assert_not_called()


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_update_accepts_content_with_exactly_the_maximum_length(mock_gateway):
    result = await PersonalityService.update_personality("x" * MAX_PERSONALITY_LENGTH)

    assert result["success"] is True


@pytest.mark.asyncio
@patch("service.personality_service.PersonalityGateway")
async def test_update_reports_error_when_file_cannot_be_written(mock_gateway):
    mock_gateway.write.side_effect = PermissionError("sem permissão")

    result = await PersonalityService.update_personality("Fazes piadas.")

    assert result == {"success": False, "error": "personality_not_saved"}
