import pytest

from data.gateway.memory_gateway import MemoryGateway


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr("config.connections.sqlite_connection.AYAN_DB_PATH", tmp_path / "ayan" / "ayan.db")


def test_add_then_list_returns_memories_in_insertion_order():
    first = MemoryGateway.add("Prefere respostas curtas.")
    second = MemoryGateway.add("Trabalha na Almovi.")

    assert [m.content for m in MemoryGateway.list_all()] == ["Prefere respostas curtas.", "Trabalha na Almovi."]
    assert second.id > first.id
    assert first.created_at


def test_get_by_id_returns_none_when_memory_does_not_exist():
    assert MemoryGateway.get_by_id(999) is None


def test_delete_removes_memory_and_reports_whether_it_existed():
    memory = MemoryGateway.add("Gosta de tópicos.")

    assert MemoryGateway.delete(memory.id) is True
    assert MemoryGateway.delete(memory.id) is False
    assert MemoryGateway.list_all() == []


def test_content_with_sql_syntax_is_stored_literally():
    payload = "x'); DROP TABLE memories; --"

    MemoryGateway.add(payload)

    assert [m.content for m in MemoryGateway.list_all()] == [payload]
