import pytest

from data.gateway.filesystem_gateway import FilesystemGateway


def test_read_bytes_returns_at_most_max_bytes_and_real_total_size(tmp_path):
    (tmp_path / "log.txt").write_bytes(b"0123456789")

    content = FilesystemGateway.read_bytes(tmp_path / "log.txt", max_bytes=4)

    assert content.data == b"0123"
    assert content.total_size == 10


def test_read_bytes_raises_os_error_for_missing_file(tmp_path):
    with pytest.raises(OSError):
        FilesystemGateway.read_bytes(tmp_path / "nao_existe.txt", max_bytes=10)


def test_list_directory_returns_files_with_size_and_folders(tmp_path):
    (tmp_path / "relatorio.txt").write_bytes(b"abc")
    (tmp_path / "fotos").mkdir()

    entries = {entry.name: entry for entry in FilesystemGateway.list_directory(tmp_path)}

    assert entries["relatorio.txt"].is_dir is False
    assert entries["relatorio.txt"].size == 3
    assert entries["fotos"].is_dir is True
    assert entries["fotos"].size is None
