import os
from pathlib import Path

from data.model.computer_model import DirectoryEntry, FileContent


class FilesystemGateway:
    @staticmethod
    def read_bytes(path: Path, max_bytes: int) -> FileContent:
        with open(path, "rb") as file:
            total_size = os.fstat(file.fileno()).st_size
            return FileContent(data=file.read(max_bytes), total_size=total_size)

    @staticmethod
    def list_directory(path: Path) -> list[DirectoryEntry]:
        entries = []
        with os.scandir(path) as scanner:
            for entry in scanner:
                try:
                    is_dir = entry.is_dir()
                    size = None if is_dir else entry.stat().st_size
                except OSError:
                    is_dir, size = False, None
                entries.append(DirectoryEntry(name=entry.name, is_dir=is_dir, size=size))
        return entries
