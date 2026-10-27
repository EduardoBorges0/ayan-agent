import sys
from unittest.mock import patch

from config.builtin_mcp_servers import PROJECT_ROOT, builtin_server_configs


@patch("config.builtin_mcp_servers.user_settings")
def test_tmdb_is_not_started_without_an_api_key(mock_settings):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_settings.get_lastfm_api_key.return_value = None

    assert builtin_server_configs() == []


@patch("config.builtin_mcp_servers.user_settings")
def test_tmdb_runs_bundled_server_with_key_in_its_environment(mock_settings):
    mock_settings.get_tmdb_api_key.return_value = "chave-tmdb"
    mock_settings.get_lastfm_api_key.return_value = None

    [server] = builtin_server_configs()

    assert server.name == "tmdb"
    assert server.command == sys.executable
    assert server.args == ["-m", "mcp_servers.tmdb_mcp"]
    assert server.cwd == str(PROJECT_ROOT)
    assert server.env == {"TMDB_API_KEY": "chave-tmdb"}
    assert server.trusted is True
    assert (PROJECT_ROOT / "mcp_servers" / "tmdb_mcp" / "__main__.py").exists()


@patch("config.builtin_mcp_servers.user_settings")
def test_lastfm_is_not_started_without_an_api_key(mock_settings):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_settings.get_lastfm_api_key.return_value = None

    assert builtin_server_configs() == []


@patch("config.builtin_mcp_servers.user_settings")
def test_lastfm_runs_bundled_server_with_key_in_its_environment(mock_settings):
    mock_settings.get_tmdb_api_key.return_value = None
    mock_settings.get_lastfm_api_key.return_value = "chave-lastfm"

    [server] = builtin_server_configs()

    assert server.name == "lastfm"
    assert server.command == sys.executable
    assert server.args == ["-m", "mcp_servers.lastfm_mcp"]
    assert server.cwd == str(PROJECT_ROOT)
    assert server.env == {"LASTFM_API_KEY": "chave-lastfm"}
    assert server.trusted is True
    assert (PROJECT_ROOT / "mcp_servers" / "lastfm_mcp" / "__main__.py").exists()


@patch("config.builtin_mcp_servers.user_settings")
def test_tmdb_and_lastfm_can_run_together(mock_settings):
    mock_settings.get_tmdb_api_key.return_value = "chave-tmdb"
    mock_settings.get_lastfm_api_key.return_value = "chave-lastfm"

    assert [server.name for server in builtin_server_configs()] == ["tmdb", "lastfm"]
