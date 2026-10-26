from dataclasses import dataclass


@dataclass(frozen=True)
class FileContent:
    data: bytes
    total_size: int


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    is_dir: bool
    size: int | None


@dataclass(frozen=True)
class CommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
