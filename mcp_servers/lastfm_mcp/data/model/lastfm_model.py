from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Tag:
    name: str
    url: str | None = None
    count: int | None = None


@dataclass(frozen=True)
class ArtistRef:
    name: str
    url: str | None = None
    mbid: str | None = None
    match: float | None = None
    listeners: int | None = None


@dataclass(frozen=True)
class ArtistInfo:
    name: str
    url: str | None = None
    mbid: str | None = None
    listeners: int | None = None
    playcount: int | None = None
    user_playcount: int | None = None
    on_tour: bool | None = None
    tags: list[Tag] = field(default_factory=list)
    similar: list[ArtistRef] = field(default_factory=list)
    summary: str | None = None
    content: str | None = None


@dataclass(frozen=True)
class ArtistCorrection:
    name: str
    corrected: bool
    mbid: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class AlbumRef:
    name: str
    artist: str | None = None
    url: str | None = None
    mbid: str | None = None
    playcount: int | None = None


@dataclass(frozen=True)
class TrackRef:
    name: str
    artist: str | None = None
    url: str | None = None
    mbid: str | None = None
    playcount: int | None = None
    listeners: int | None = None
    rank: int | None = None
    duration_seconds: int | None = None


@dataclass(frozen=True)
class AlbumInfo:
    name: str
    artist: str | None = None
    url: str | None = None
    mbid: str | None = None
    listeners: int | None = None
    playcount: int | None = None
    user_playcount: int | None = None
    published: str | None = None
    tags: list[Tag] = field(default_factory=list)
    tracks: list[TrackRef] = field(default_factory=list)
    summary: str | None = None
    content: str | None = None


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    page: int
    total_pages: int
    total: int
