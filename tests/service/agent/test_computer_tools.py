import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from data.model.agent_model import ToolContext
from data.model.computer_model import CommandResult, DirectoryEntry, FileContent
from service.agent.computer_tools import (
    COMPUTER_TOOLS,
    MAX_FILE_BYTES,
    REFUSED,
    initial_approved_folders,
    is_broad_folder,
)

TOOLS = {tool.definition.name: tool for tool in COMPUTER_TOOLS}


def _context(
    workspace: Path, approve: bool = False, approved: set[Path] | None = None
) -> tuple[ToolContext, MagicMock]:
    confirm = MagicMock(return_value=approve)
    folders = {workspace.resolve()} if approved is None else approved
    return ToolContext(workspace=workspace, confirm=confirm, approved_folders=folders), confirm


def _args(**values) -> str:
    return json.dumps(values)


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    home_dir = tmp_path / "Users" / "eduardo"
    home_dir.mkdir(parents=True)
    monkeypatch.setattr("service.agent.computer_tools._home", lambda: home_dir)
    return home_dir


def test_project_folder_is_approved_from_the_start(home):
    project = home / "Documents" / "code" / "api"
    project.mkdir(parents=True)

    assert initial_approved_folders(project) == {project.resolve()}


@pytest.mark.parametrize("folder", ["home", "parent_of_home", "drive_root"])
def test_broad_folders_are_never_approved_from_the_start(home, folder):
    workspace = {"home": home, "parent_of_home": home.parent, "drive_root": Path(home.anchor)}[folder]

    assert is_broad_folder(workspace) is True
    assert initial_approved_folders(workspace) == set()


@pytest.mark.asyncio
async def test_read_file_in_approved_folder_does_not_ask_for_confirmation(tmp_path):
    (tmp_path / "notas.txt").write_text("Revisão da grua concluída.", encoding="utf-8")
    context, confirm = _context(tmp_path)

    outcome = await TOOLS["read_file"].run(_args(path="notas.txt"), context)

    assert outcome.output == "Revisão da grua concluída."
    confirm.assert_not_called()


@pytest.mark.asyncio
async def test_approving_a_folder_once_covers_its_subfolders_for_the_session(home):
    project = home / "Documents" / "code" / "api"
    (project / "src").mkdir(parents=True)
    (project / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    context, confirm = _context(home, approve=True, approved=set())

    await TOOLS["list_directory"].run(_args(path=str(project)), context)
    outcome = await TOOLS["read_file"].run(_args(path=str(project / "src" / "main.py")), context)

    assert outcome.output == "print('ok')"
    confirm.assert_called_once()
    assert "aceder à pasta" in confirm.call_args.args[0]
    assert context.approved_folders == {project.resolve()}


@pytest.mark.asyncio
@patch("service.agent.computer_tools.FilesystemGateway")
async def test_refused_folder_is_not_read_nor_remembered(mock_fs, home):
    project = home / "Documents"
    context, _ = _context(home, approve=False, approved=set())

    outcome = await TOOLS["read_file"].run(_args(path=str(project / "segredos.txt")), context)

    assert outcome.output == REFUSED
    assert context.approved_folders == set()
    mock_fs.read_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_broad_folder_access_asks_every_time_and_is_never_remembered(home):
    context, confirm = _context(home, approve=True, approved=set())

    await TOOLS["list_directory"].run(_args(path="."), context)
    await TOOLS["list_directory"].run(_args(path="."), context)

    assert confirm.call_count == 2
    assert "só para este acesso" in confirm.call_args.args[0]
    assert context.approved_folders == set()


@pytest.mark.asyncio
async def test_parent_folder_escape_is_not_covered_by_approved_folder(tmp_path):
    workspace = tmp_path / "projeto"
    workspace.mkdir()
    (tmp_path / "fora.txt").write_text("x", encoding="utf-8")
    context, confirm = _context(workspace, approve=False)

    outcome = await TOOLS["read_file"].run(_args(path="../fora.txt"), context)

    assert outcome.output == REFUSED
    confirm.assert_called_once()


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
    assert outcome.event.startswith("Não consegui ler")


@pytest.mark.asyncio
async def test_list_directory_failure_is_shown_to_user(tmp_path):
    context, _ = _context(tmp_path)

    outcome = await TOOLS["list_directory"].run(_args(path="code/api"), context)

    assert outcome.output.startswith("Erro ao listar")
    assert outcome.event.startswith(f"Não consegui listar {(tmp_path / 'code' / 'api').resolve()}")


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
