from mcp_servers.lastfm_mcp.config.connections.lastfm_connection import LastFmConnect
from mcp_servers.lastfm_mcp.data.model.lastfm_model import AlbumInfo, AlbumRef, Page, Tag, TrackRef
from mcp_servers.lastfm_mcp.data.gateway.lastfm_mapping import (
    clean_text,
    map_items,
    map_tag,
    name_of,
    non_empty,
    search_page,
    section,
    to_int,
)


def _identity(artist: str | None, album: str | None, mbid: str | None, autocorrect: bool) -> dict[str, str | int]:
    params: dict[str, str | int] = {"mbid": mbid} if mbid else {"artist": artist or "", "album": album or ""}
    if autocorrect:
        params["autocorrect"] = 1
    return params


def _map_track(item: dict) -> TrackRef:
    attr = item.get("@attr")
    return TrackRef(
        name=item["name"],
        artist=name_of(item.get("artist")),
        url=non_empty(item.get("url")),
        mbid=non_empty(item.get("mbid")),
        rank=to_int(attr.get("rank")) if isinstance(attr, dict) else None,
        duration_seconds=to_int(item.get("duration")),
    )


def _map_search_album(item: dict) -> AlbumRef:
    return AlbumRef(
        name=item["name"],
        artist=name_of(item.get("artist")),
        url=non_empty(item.get("url")),
        mbid=non_empty(item.get("mbid")),
    )


class AlbumGateway:
    """Entidade de negócio: álbum (métodos album.* do Last.fm, só leitura)."""

    @staticmethod
    async def get_info(
        artist: str | None,
        album: str | None,
        mbid: str | None,
        lang: str | None,
        username: str | None,
        autocorrect: bool,
    ) -> AlbumInfo | None:
        params = _identity(artist, album, mbid, autocorrect)
        if lang:
            params["lang"] = lang
        if username:
            params["username"] = username
        payload = await LastFmConnect.request("album.getInfo", params)
        raw = section(payload, "album") if payload else None
        if raw is None:
            return None
        wiki = raw.get("wiki") if isinstance(raw.get("wiki"), dict) else {}
        return AlbumInfo(
            name=raw.get("name", ""),
            artist=name_of(raw.get("artist")),
            url=non_empty(raw.get("url")),
            mbid=non_empty(raw.get("mbid")),
            listeners=to_int(raw.get("listeners")),
            playcount=to_int(raw.get("playcount")),
            user_playcount=to_int(raw.get("userplaycount")),
            published=non_empty(wiki.get("published")),
            tags=map_items(raw.get("tags"), "tag", map_tag),
            tracks=map_items(raw.get("tracks"), "track", _map_track),
            summary=clean_text(wiki.get("summary")),
            content=clean_text(wiki.get("content")),
        )

    @staticmethod
    async def get_top_tags(artist: str | None, album: str | None, mbid: str | None, autocorrect: bool) -> list[Tag] | None:
        payload = await LastFmConnect.request("album.getTopTags", _identity(artist, album, mbid, autocorrect))
        container = section(payload, "toptags") if payload else None
        if container is None:
            return None
        return map_items(container, "tag", map_tag)

    @staticmethod
    async def get_user_tags(
        artist: str | None, album: str | None, mbid: str | None, user: str, autocorrect: bool
    ) -> list[Tag] | None:
        params = {**_identity(artist, album, mbid, autocorrect), "user": user}
        payload = await LastFmConnect.request("album.getTags", params)
        container = section(payload, "tags") if payload else None
        if container is None:
            return None
        return map_items(container, "tag", map_tag)

    @staticmethod
    async def search(album: str, page: int, limit: int) -> Page[AlbumRef]:
        payload = await LastFmConnect.request("album.search", {"album": album, "page": page, "limit": limit})
        results = section(payload, "results") if payload else None
        if results is None:
            return Page(items=[], page=page, total_pages=1, total=0)
        return search_page(results, map_items(results.get("albummatches"), "album", _map_search_album))
