from typing import Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    page: int
    total_pages: int
    total_results: int
    results: list[T]


class CastMember(BaseModel):
    name: str
    character: str | None


class MovieSummary(BaseModel):
    id: int
    title: str
    original_title: str | None
    release_date: str | None
    overview: str | None
    vote_average: float | None
    poster_url: str | None
    vote_count: int | None = None


class MovieDetails(MovieSummary):
    tagline: str | None
    runtime_minutes: int | None
    genres: list[str]
    status: str | None
    directors: list[str]
    cast: list[CastMember]
    trailer_url: str | None
    imdb_url: str | None
    homepage: str | None


class TvShowSummary(BaseModel):
    id: int
    name: str
    original_name: str | None
    first_air_date: str | None
    overview: str | None
    vote_average: float | None
    poster_url: str | None
    vote_count: int | None = None


class TvShowDetails(TvShowSummary):
    tagline: str | None
    genres: list[str]
    status: str | None
    last_air_date: str | None
    number_of_seasons: int | None
    number_of_episodes: int | None
    creators: list[str]
    networks: list[str]
    cast: list[CastMember]
    trailer_url: str | None


class PersonSummary(BaseModel):
    id: int
    name: str
    known_for_department: str | None
    known_for: list[str]
    profile_url: str | None


class MediaItem(BaseModel):
    media_type: Literal["movie", "tv", "person"]
    id: int
    title: str
    date: str | None
    overview: str | None
    vote_average: float | None
    image_url: str | None
    vote_count: int | None = None


# Nome anterior de MediaItem, mantido por compatibilidade.
TrendingItem = MediaItem


class GenreSummary(BaseModel):
    id: int
    name: str


class KeywordSummary(BaseModel):
    id: int
    name: str


class CompanySummary(BaseModel):
    id: int
    name: str
    origin_country: str | None


class Credit(BaseModel):
    media_type: Literal["movie", "tv"]
    id: int
    title: str
    date: str | None
    role: str | None
    vote_average: float | None
    vote_count: int | None
