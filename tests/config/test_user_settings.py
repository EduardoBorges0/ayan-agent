from unittest.mock import patch

from keyring.errors import PasswordDeleteError

from config import user_settings


@patch("config.user_settings.keyring")
@patch("config.user_settings.OPENAI_API_KEY", "chave-do-ambiente")
def test_env_api_key_takes_priority_over_stored_key(mock_keyring):
    mock_keyring.get_password.return_value = "chave-guardada"

    assert user_settings.get_api_key() == "chave-do-ambiente"


@patch("config.user_settings.keyring")
@patch("config.user_settings.OPENAI_API_KEY", None)
def test_stored_key_is_read_from_keyring_when_env_is_empty(mock_keyring):
    mock_keyring.get_password.return_value = "chave-guardada"

    assert user_settings.get_api_key() == "chave-guardada"
    mock_keyring.get_password.assert_called_once_with("ayan", "openai_api_key")


@patch("config.user_settings.keyring")
def test_delete_api_key_returns_false_when_nothing_is_stored(mock_keyring):
    mock_keyring.delete_password.side_effect = PasswordDeleteError()

    assert user_settings.delete_api_key() is False


@patch("config.user_settings.OPENAI_MODEL", None)
def test_saved_model_is_read_back_from_user_config_dir(tmp_path):
    with patch("config.user_settings.USER_CONFIG_DIR", tmp_path / "ayan"):
        assert user_settings.get_model() is None

        user_settings.save_model("modelo-de-teste")

        assert user_settings.get_model() == "modelo-de-teste"
