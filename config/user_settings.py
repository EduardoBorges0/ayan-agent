import json

import keyring
from keyring.errors import PasswordDeleteError

from load_env import OPENAI_API_KEY, OPENAI_MODEL, USER_CONFIG_DIR

_KEYRING_SERVICE = "ayan"
_KEYRING_USERNAME = "openai_api_key"


def _settings_path():
    return USER_CONFIG_DIR / "settings.json"


def api_key_comes_from_env() -> bool:
    return bool(OPENAI_API_KEY)


def get_api_key() -> str | None:
    return OPENAI_API_KEY or keyring.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)


def save_api_key(api_key: str) -> None:
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, api_key)


def delete_api_key() -> bool:
    try:
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except PasswordDeleteError:
        return False
    return True


def get_model() -> str | None:
    if OPENAI_MODEL:
        return OPENAI_MODEL
    path = _settings_path()
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("model")


def save_model(model: str) -> None:
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps({"model": model}), encoding="utf-8")
