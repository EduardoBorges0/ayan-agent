"""Validação e normalização do input recebido do agente (nunca confiar nele)."""

import re

MAX_TEXT_LENGTH = 200
MAX_LIMIT = 50
DEFAULT_LIMIT = 10
MAX_PAGE = 1000

_MBID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_USERNAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,14}$")
_LANG = re.compile(r"^[a-z]{2}$")


class InvalidInputError(ValueError):
    pass


def normalize_text(value: object, field_name: str, *, required: bool = False) -> str | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        if required:
            raise InvalidInputError(f"O campo '{field_name}' é obrigatório.")
        return None
    if len(text) > MAX_TEXT_LENGTH:
        raise InvalidInputError(f"O campo '{field_name}' excede {MAX_TEXT_LENGTH} caracteres.")
    if any(ord(char) < 32 for char in text):
        raise InvalidInputError(f"O campo '{field_name}' contém caracteres de controlo.")
    return text


def normalize_mbid(value: object) -> str | None:
    text = normalize_text(value, "mbid")
    if text is None:
        return None
    if not _MBID.match(text):
        raise InvalidInputError("O 'mbid' tem de ser um UUID do MusicBrainz.")
    return text.lower()


def normalize_username(value: object, *, required: bool = False) -> str | None:
    text = normalize_text(value, "user" if required else "username", required=required)
    if text is not None and not _USERNAME.match(text):
        raise InvalidInputError("O nome de utilizador do Last.fm só pode ter letras, números, '-' e '_' (2 a 15 caracteres).")
    return text


def normalize_lang(value: object) -> str | None:
    text = normalize_text(value, "lang")
    if text is None:
        return None
    text = text.lower()
    if not _LANG.match(text):
        raise InvalidInputError("O 'lang' tem de ser um código de idioma de 2 letras (ex.: 'pt', 'en').")
    return text


def normalize_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_LIMIT:
        raise InvalidInputError(f"O 'limit' tem de ser um número entre 1 e {MAX_LIMIT}.")
    return value


def normalize_page(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_PAGE:
        raise InvalidInputError(f"A 'page' tem de ser um número entre 1 e {MAX_PAGE}.")
    return value


def artist_identity(artist: object, mbid: object) -> tuple[str | None, str | None]:
    name = normalize_text(artist, "artist")
    normalized_mbid = normalize_mbid(mbid)
    if name is None and normalized_mbid is None:
        raise InvalidInputError("Indica o nome do artista ('artist') ou o 'mbid'.")
    return name, normalized_mbid


def album_identity(artist: object, album: object, mbid: object) -> tuple[str | None, str | None, str | None]:
    normalized_mbid = normalize_mbid(mbid)
    required = normalized_mbid is None
    return (
        normalize_text(artist, "artist", required=required),
        normalize_text(album, "album", required=required),
        normalized_mbid,
    )
