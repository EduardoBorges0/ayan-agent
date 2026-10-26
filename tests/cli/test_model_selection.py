import asyncio
from unittest.mock import AsyncMock, patch

from cli.chat_cli import choose_model, configure

MODELS = ["gpt-4o", "gpt-4o-mini", "o3"]


def _answers(*lines: str):
    remaining = list(lines)
    return lambda _prompt: remaining.pop(0)


def test_choose_model_returns_model_for_typed_number():
    assert choose_model(MODELS, None, _answers("2"), lambda _: None) == "gpt-4o-mini"


def test_choose_model_keeps_current_model_on_enter():
    assert choose_model(MODELS, "o3", _answers(""), lambda _: None) == "o3"


def test_choose_model_asks_again_on_invalid_answer():
    output: list[str] = []

    model = choose_model(MODELS, None, _answers("", "9", "abc", "1"), output.append)

    assert model == "gpt-4o"
    assert output.count("Escreve um número entre 1 e 3.") == 3


def test_choose_model_ignores_enter_when_current_model_is_not_in_list():
    model = choose_model(MODELS, "gpt4o-mini", _answers("", "3"), lambda _: None)

    assert model == "o3"


@patch("cli.chat_cli.OpenAIConnect")
@patch("cli.chat_cli.choose_model", return_value="gpt-4o-mini")
@patch("cli.chat_cli.ChatService")
@patch("cli.chat_cli._prompt_api_key", side_effect=["chave-rejeitada", "chave-valida"])
@patch("cli.chat_cli.user_settings")
def test_configure_never_saves_a_rejected_key(mock_settings, _prompt, mock_service, _choose, _connect):
    mock_settings.get_api_key.return_value = None
    mock_settings.get_model.return_value = None
    mock_settings.api_key_comes_from_env.return_value = False
    mock_service.available_models = AsyncMock(side_effect=[
        {"success": False, "error": "llm_auth_failed"},
        {"success": True, "data": MODELS},
    ])

    configure(asyncio.run)

    mock_settings.save_api_key.assert_called_once_with("chave-valida")
    mock_settings.save_model.assert_called_once_with("gpt-4o-mini")
