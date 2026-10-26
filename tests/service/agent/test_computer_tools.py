import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data.model.agent_model import ToolContext
from data.model.computer_model import CommandResult, DirectoryEntry, FileContent
from service.agent.computer_tools import COMPUTER_TOOLS, MAX_FILE_BYTES, REFUSED

TOOLS = {tool.definition.name: tool for tool in COMPUTER_TOOLS}


def _context(workspace: Path, approve: bool = False) -> tuple[ToolContext, MagicMock]:
    confirm = MagicMock(return_value=approve)
    return ToolContext(workspace=workspace, confirm=confirm), confirm


def _args(**values) -> str:
    return json.dumps(values)


@pytest.mark.asyncio
async def test_read_file_inside_workspace_does_not_ask_for_confirmation(tmp_path):
    (tmp_path / "notas.txt").write_text("Revisão da grua concluída.", encoding="utf-8")
    context, confirm = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="notas.txt"), context)

    assert outcome.output == "Revisão da grua concluída."
    confirm.assert_not_called()


@pytest.mark.asyncio
@patch("service.agent.computer_tools.FilesystemGateway")
async def test_read_file_outside_workspace_is_not_read_when_user_refuses(mock_fs, tmp_path):
    context, confirm = _context(tmp_path / "projeto", approve=False)

    outcome = await TOOLS["read_file"].run(_args(path=str(tmp_path / "segredos.txt")), context)

    assert outcome.output == REFUSED
    assert "fora da pasta atual" in confirm.call_args.args[0]
    mock_fs.read_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_parent_folder_escape_counts_as_outside_workspace(tmp_path):
    workspace = tmp_path / "projeto"
    workspace.mkdir()
    (tmp_path / "fora.txt").write_text("x", encoding="utf-8")
    context, confirm = _context(workspace, approve=False)

    outcome = await TOOLS["read_file"].run(_args(path="../fora.txt"), context)

    assert outcome.output == REFUSED
    confirm.assert_called_once()


@pytest.mark.asyncio
async def test_read_file_outside_workspace_is_read_when_user_approves(tmp_path):
    outside = tmp_path / "fora.txt"
    outside.write_text("conteúdo", encoding="utf-8")
    context, _ = _context(tmp_path / "projeto", approve=True)

    outcome = await TOOLS["read_file"].run(_args(path=str(outside)), context)

    assert outcome.output == "conteúdo"


@pytest.mark.asyncio
async def test_read_file_rejects_binary_files(tmp_path):
    (tmp_path / "foto.jpg").write_bytes(b"\xff\xd8\x00\x10JFIF")
    context, _ = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="foto.jpg"), context)

    assert "ficheiro binário" in outcome.output


@pytest.mark.asyncio
async def test_read_file_decodes_windows_1252_files(tmp_path):
    (tmp_path / "antigo.txt").write_bytes("Manutenção".encode("cp1252"))
    context, _ = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="antigo.txt"), context)

    assert outcome.output == "Manutenção"


@pytest.mark.asyncio
@patch("service.agent.computer_tools.FilesystemGateway")
async def test_truncation_in_the_middle_of_a_utf8_character_drops_only_that_character(mock_fs, tmp_path):
    data = ("a" * (MAX_FILE_BYTES - 1)).encode() + "ç".encode()[:1]
    mock_fs.read_bytes.return_value = FileContent(data=data, total_size=MAX_FILE_BYTES + 10)
    context, _ = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="grande.txt"), context)

    assert outcome.output.startswith("a" * (MAX_FILE_BYTES - 1) + "\n[Ficheiro truncado")


@pytest.mark.asyncio
@patch("service.agent.computer_tools.FilesystemGateway")
async def test_read_file_marks_truncated_content(mock_fs, tmp_path):
    mock_fs.read_bytes.return_value = FileContent(data=b"a" * MAX_FILE_BYTES, total_size=MAX_FILE_BYTES + 500)
    context, _ = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="grande.log"), context)

    assert outcome.output.endswith(f"[Ficheiro truncado: mostrados {MAX_FILE_BYTES} de {MAX_FILE_BYTES + 500} bytes.]")


@pytest.mark.asyncio
async def test_read_file_reports_missing_file_to_model(tmp_path):
    context, _ = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="nao_existe.txt"), context)

    assert outcome.output.startswith("Erro ao ler")
    assert outcome.event is None


@pytest.mark.asyncio
@patch("service.agent.computer_tools.FilesystemGateway")
async def test_list_directory_shows_folders_first(mock_fs, tmp_path):
    mock_fs.list_directory.return_value = [
        DirectoryEntry("zeta.txt", False, 10),
        DirectoryEntry("docs", True, None),
        DirectoryEntry("Alfa.txt", False, 5),
    ]
    context, _ = _context(tmp_path)

    outcome = await TOOLS["list_directory"].run(_args(path="."), context)

    assert outcome.output.splitlines()[1:] == ["[pasta] docs", "Alfa.txt (5 bytes)", "zeta.txt (10 bytes)"]


@pytest.mark.asyncio
@patch("service.agent.computer_tools.PowerShellGateway")
async def test_refused_command_is_never_executed(mock_ps, tmp_path):
    context, confirm = _context(tmp_path, approve=False)

    outcome = await TOOLS["run_powershell"].run(_args(command="Remove-Item *.log"), context)

    assert outcome.output == REFUSED
    assert "Remove-Item *.log" in confirm.call_args.args[0]
    mock_ps.run.assert_not_called()


@pytest.mark.asyncio
@patch("service.agent.computer_tools.PowerShellGateway")
async def test_approved_command_runs_in_workspace_and_returns_output(mock_ps, tmp_path):
    mock_ps.run.return_value = CommandResult(exit_code=0, stdout="ok\n", stderr="", timed_out=False)
    context, _ = _context(tmp_path, approve=True)

    outcome = await TOOLS["run_powershell"].run(_args(command="Get-Date"), context)

    assert mock_ps.run.call_args.args[:2] == ("Get-Date", tmp_path)
    assert outcome.output == "O comando terminou com o código 0.\nSaída:\nok\n"
    assert outcome.event == "O comando terminou com o código 0."


@pytest.mark.asyncio
@patch("service.agent.computer_tools.PowerShellGateway")
async def test_command_timeout_is_reported(mock_ps, tmp_path):
    mock_ps.run.return_value = CommandResult(exit_code=None, stdout="", stderr="", timed_out=True)
    context, _ = _context(tmp_path, approve=True)

    outcome = await TOOLS["run_powershell"].run(_args(command="Start-Sleep 999"), context)

    assert outcome.output.startswith("O comando foi interrompido")


@pytest.mark.asyncio
@patch("service.agent.computer_tools.PowerShellGateway")
async def test_empty_command_is_rejected_without_asking(mock_ps, tmp_path):
    context, confirm = _context(tmp_path, approve=True)

    outcome = await TOOLS["run_powershell"].run(_args(command="   "), context)

    assert outcome.output == "Erro: o comando está vazio."
    confirm.assert_not_called()
    mock_ps.run.assert_not_called()
