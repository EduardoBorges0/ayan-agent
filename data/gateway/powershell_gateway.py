import subprocess
from pathlib import Path

from data.model.computer_model import CommandResult

# Sem isto, o Windows PowerShell 5.1 escreve para o pipe na code page da consola e os acentos chegam estragados.
_UTF8_OUTPUT = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "


def _decode(output: bytes | None) -> str:
    return (output or b"").decode("utf-8", errors="replace")


class PowerShellGateway:
    @staticmethod
    def run(command: str, cwd: Path, timeout_seconds: int) -> CommandResult:
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _UTF8_OUTPUT + command],
                cwd=cwd,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(exit_code=None, stdout=_decode(exc.stdout), stderr=_decode(exc.stderr), timed_out=True)
        return CommandResult(
            exit_code=completed.returncode,
            stdout=_decode(completed.stdout),
            stderr=_decode(completed.stderr),
            timed_out=False,
        )
