import pytest

from data.gateway.personality_gateway import PersonalityGateway


@pytest.fixture(autouse=True)
def personality_path(tmp_path, monkeypatch):
    path = tmp_path / "ayan" / "personality.md"
    monkeypatch.setattr("data.gateway.personality_gateway.PERSONALITY_PATH", path)
    return path


def test_read_returns_none_when_file_does_not_exist():
    assert PersonalityGateway.read() is None


def test_write_creates_missing_folder_and_read_returns_same_text(personality_path):
    PersonalityGateway.write("Fazes piadas sobre os temas.\nUsas exemplos do dia a dia.")

    assert personality_path.exists()
    assert PersonalityGateway.read() == "Fazes piadas sobre os temas.\nUsas exemplos do dia a dia."


def test_write_replaces_previous_content_and_leaves_no_temporary_file(personality_path):
    PersonalityGateway.write("Primeira versão.")
    PersonalityGateway.write("Segunda versão.")

    assert PersonalityGateway.read() == "Segunda versão."
    assert [path.name for path in personality_path.parent.iterdir()] == ["personality.md"]


def test_accents_are_stored_as_utf8(personality_path):
    PersonalityGateway.write("Explicas com paciência e humor — sem rodeios.")

    assert "paciência" in personality_path.read_bytes().decode("utf-8")


def test_read_accepts_file_saved_with_byte_order_mark(personality_path):
    personality_path.parent.mkdir(parents=True)
    personality_path.write_bytes("\ufeffSê direto.".encode("utf-8"))

    assert PersonalityGateway.read() == "Sê direto."


def test_read_raises_when_file_is_not_valid_utf8(personality_path):
    personality_path.parent.mkdir(parents=True)
    personality_path.write_bytes("Sê direto.".encode("latin-1"))

    with pytest.raises(UnicodeDecodeError):
        PersonalityGateway.read()
