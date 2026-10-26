import subprocess
from unittest.mock import MagicMock, patch

import pytest

from data.gateway.powershell_gateway import PowerShellGateway


@patch("data.gateway.powershell_gateway.subprocess.run")
def test_run_calls_powershell_without_profile_or_interaction_in_given_folder(mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0, stdout="olá".encode(), stderr=b"")

    result = PowerShellGateway.run("Get-Date", tmp_path, timeout_seconds=30)

    args = mock_run.call_args.args[0]
    assert args[:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
    assert args[4].endswith("Get-Date")
    assert mock_run.call_args.kwargs["cwd"] == tmp_path
    assert mock_run.call_args.kwargs["timeout"] == 30
    assert result.exit_code == 0
    assert result.stdout == "olá"
    assert result.timed_out is False


@patch("data.gateway.powershell_gateway.subprocess.run")
def test_run_reports_timeout_with_partial_output(mock_run, tmp_path):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="powershell.exe", timeout=5, output=b"parcial")

    result = PowerShellGateway.run("Start-Sleep 60", tmp_path, timeout_seconds=5)

    assert result.timed_out is True
    assert result.exit_code is None
    assert result.stdout == "parcial"


@pytest.mark.integration
def test_run_real_powershell_returns_utf8_output_and_exit_code(tmp_path):
    result = PowerShellGateway.run("Write-Output 'Manutenção'; exit 3", tmp_path, timeout_seconds=60)

    assert result.stdout.strip() == "Manutenção"
    assert result.exit_code == 3
