import json

import pytest

from config import mcp_settings
from data.model.mcp_model import McpServerConfig


@pytest.fixture
def config_path(tmp_path, monkeypatch):
    path = tmp_path / "ayan" / "mcp.json"
    monkeypatch.setattr("config.mcp_settings.MCP_CONFIG_PATH", path)
    return path


def test_missing_file_means_no_servers(config_path):
    assert mcp_settings.load_server_configs() == ([], [])


def test_invalid_json_is_reported_as_warning(config_path):
    config_path.parent.mkdir(parents=True)
    config_path.write_text("{ isto não é json", encoding="utf-8")

    servers, warnings = mcp_settings.load_server_configs()

    assert servers == []
    assert "não é um JSON válido" in warnings[0]


def test_badly_configured_server_does_not_block_the_others(config_path):
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps({"mcpServers": {
        "tmdb": {"command": "python", "args": ["-m", "tmdb_mcp"], "cwd": "C:/tmdb-mcp"},
        "partido": {"args": ["sem comando"]},
        "nome inválido": {"command": "x"},
    }}), encoding="utf-8")

    servers, warnings = mcp_settings.load_server_configs()

    assert [server.name for server in servers] == ["tmdb"]
    assert servers[0].args == ["-m", "tmdb_mcp"]
    assert len(warnings) == 2


def test_add_and_remove_server_round_trip(config_path):
    mcp_settings.add_server(McpServerConfig(name="tmdb", command="python", args=["-m", "tmdb_mcp"], cwd="C:/x"))

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved == {"mcpServers": {"tmdb": {"command": "python", "args": ["-m", "tmdb_mcp"], "cwd": "C:/x"}}}

    assert mcp_settings.remove_server("tmdb") is True
    assert mcp_settings.remove_server("tmdb") is False
    assert mcp_settings.load_server_configs() == ([], [])
