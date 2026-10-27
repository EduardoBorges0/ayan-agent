"""Conversão do JSON do Last.fm (campos aninhados, números em texto, listas que às vezes
vêm como objeto único ou como string vazia) para os modelos internos."""

import html
import re
from collections.abc import Callable
from typing import TypeVar

from mcp_servers.lastfm_mcp.data.model.lastfm_model import ArtistRef, Page, Tag

T = TypeVar("T")

_READ_MORE_LINK = re.compile(r"<a\s[^>]*>\s*Read more on Last\.fm\s*</a>", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")


def as_list(value: object) -> list:
    if value is None or value == "":
        return []
    return value if isinstance(value, list) else [value]


def non_empty(value: object) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    return None


def to_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_bool(value: object) -> bool | None:
    if value in ("1", 1, True):
        return True
    if value in ("0", 0, False):
        return False
    return None


def clean_text(value: object) -> str | None:
    """Remove o HTML das biografias/wikis e o link 'Read more on Last.fm'."""
    if not isinstance(value, str):
        return None
    text = _READ_MORE_LINK.sub("", value)
    text = html.unescape(_HTML_TAG.sub("", text)).strip()
    return text or None


def section(payload: dict, key: str) -> dict | None:
    value = payload.get(key)
    return value if isinstance(value, dict) else None


def name_of(value: object) -> str | None:
    """O artista aparece ora como texto, ora como objeto {'name': ...}."""
    if isinstance(value, dict):
        return non_empty(value.get("name"))
    return non_empty(value)


def map_items(container: object, key: str, mapper: Callable[[dict], T]) -> list[T]:
    if not isinstance(container, dict):
        return []
    return [mapper(item) for item in as_list(container.get(key)) if isinstance(item, dict) and item.get("name")]


def map_tag(item: dict) -> Tag:
    return Tag(name=item["name"], url=non_empty(item.get("url")), count=to_int(item.get("count")))


def map_artist_ref(item: dict) -> ArtistRef:
    return ArtistRef(
        name=item["name"],
        url=non_empty(item.get("url")),
        mbid=non_empty(item.get("mbid")),
        match=to_float(item.get("match")),
        listeners=to_int(item.get("listeners")),
    )


def attr_page(container: dict, items: list[T]) -> Page[T]:
    attr = container.get("@attr")
    attr = attr if isinstance(attr, dict) else {}
    return Page(
        items=items,
        page=to_int(attr.get("page")) or 1,
        total_pages=to_int(attr.get("totalPages")) or 1,
        total=to_int(attr.get("total")) or len(items),
    )


def search_page(results: dict, items: list[T]) -> Page[T]:
    total = to_int(results.get("opensearch:totalResults")) or 0
    per_page = to_int(results.get("opensearch:itemsPerPage")) or max(len(items), 1)
    start = to_int(results.get("opensearch:startIndex")) or 0
    return Page(
        items=items,
        page=start // per_page + 1,
        total_pages=max(-(-total // per_page), 1),
        total=total,
    )
