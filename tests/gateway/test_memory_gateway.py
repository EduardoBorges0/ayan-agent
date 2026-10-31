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


def test_summary_is_none_until_a_compaction_happens():
    assert MemoryGateway.get_summary() is None


def test_compact_stores_summary_and_removes_only_memories_up_to_the_given_id():
    MemoryGateway.add("Antiga 1.")
    second = MemoryGateway.add("Antiga 2.")
    MemoryGateway.add("Recente.")

    removed = MemoryGateway.compact("Resumo das antigas.", up_to_id=second.id)

    assert removed == 2
    assert MemoryGateway.get_summary() == "Resumo das antigas."
    assert [m.content for m in MemoryGateway.list_all()] == ["Recente."]


def test_compact_replaces_the_previous_summary():
    first = MemoryGateway.add("Antiga 1.")
    MemoryGateway.compact("Primeiro resumo.", up_to_id=first.id)
    second = MemoryGateway.add("Antiga 2.")

    MemoryGateway.compact("Segundo resumo.", up_to_id=second.id)

    assert MemoryGateway.get_summary() == "Segundo resumo."


def test_summary_with_sql_syntax_is_stored_literally():
    payload = "x'); DROP TABLE memory_summary; --"
    memory = MemoryGateway.add("Qualquer coisa.")

    MemoryGateway.compact(payload, up_to_id=memory.id)

    assert MemoryGateway.get_summary() == payload
