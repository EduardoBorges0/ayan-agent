from mcp_servers.lastfm_mcp.config.connections.lastfm_connection import LastFmConnect
from mcp_servers.lastfm_mcp.data.model.lastfm_model import AlbumRef, ArtistCorrection, ArtistInfo, ArtistRef, Page, Tag, TrackRef
from mcp_servers.lastfm_mcp.data.gateway.lastfm_mapping import (
    attr_page,
    clean_text,
    map_artist_ref,
    map_items,
    map_tag,
    name_of,
    non_empty,
    search_page,
    section,
    to_bool,
    to_int,
)


def _identity(artist: str | None, mbid: str | None, autocorrect: bool) -> dict[str, str | int]:
    params: dict[str, str | int] = {"mbid": mbid} if mbid else {"artist": artist or ""}
    if autocorrect:
        params["autocorrect"] = 1
    return params


def _map_album(item: dict) -> AlbumRef:
    return AlbumRef(
        name=item["name"],
        artist=name_of(item.get("artist")),
        url=non_empty(item.get("url")),
        mbid=non_empty(item.get("mbid")),
        playcount=to_int(item.get("playcount")),
    )


def _map_track(item: dict) -> TrackRef:
    attr = item.get("@attr")
    return TrackRef(
        name=item["name"],
        artist=name_of(item.get("artist")),
        url=non_empty(item.get("url")),
        mbid=non_empty(item.get("mbid")),
        playcount=to_int(item.get("playcount")),
        listeners=to_int(item.get("listeners")),
        rank=to_int(attr.get("rank")) if isinstance(attr, dict) else None,
    )


class ArtistGateway:
    """Entidade de negócio: artista (métodos artist.* do Last.fm, só leitura)."""

    @staticmethod
    async def get_info(
        artist: str | None, mbid: str | None, lang: str | None, username: str | None, autocorrect: bool
    ) -> ArtistInfo | None:
        params = _identity(artist, mbid, autocorrect)
        if lang:
            params["lang"] = lang
        if username:
            params["username"] = username
        payload = await LastFmConnect.request("artist.getInfo", params)
        raw = section(payload, "artist") if payload else None
        if raw is None:
            return None
        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        bio = raw.get("bio") if isinstance(raw.get("bio"), dict) else {}
        return ArtistInfo(
            name=raw.get("name", ""),
            url=non_empty(raw.get("url")),
            mbid=non_empty(raw.get("mbid")),
            listeners=to_int(stats.get("listeners")),
            playcount=to_int(stats.get("playcount")),
            user_playcount=to_int(stats.get("userplaycount")),
            on_tour=to_bool(raw.get("ontour")),
            tags=map_items(raw.get("tags"), "tag", map_tag),
            similar=map_items(raw.get("similar"), "artist", map_artist_ref),
            summary=clean_text(bio.get("summary")),
            content=clean_text(bio.get("content")),
        )

    @staticmethod
    async def get_similar(artist: str | None, mbid: str | None, limit: int, autocorrect: bool) -> list[ArtistRef] | None:
        payload = await LastFmConnect.request("artist.getSimilar", {**_identity(artist, mbid, autocorrect), "limit": limit})
        container = section(payload, "similarartists") if payload else None
        if container is None:
            return None
        return map_items(container, "artist", map_artist_ref)

    @staticmethod
    async def get_top_albums(
        artist: str | None, mbid: str | None, page: int, limit: int, autocorrect: bool
    ) -> Page[AlbumRef] | None:
        params = {**_identity(artist, mbid, autocorrect), "page": page, "limit": limit}
        payload = await LastFmConnect.request("artist.getTopAlbums", params)
        container = section(payload, "topalbums") if payload else None
        if container is None:
            return None
        return attr_page(container, map_items(container, "album", _map_album))

    @staticmethod
    async def get_top_tracks(
        artist: str | None, mbid: str | None, page: int, limit: int, autocorrect: bool
    ) -> Page[TrackRef] | None:
        params = {**_identity(artist, mbid, autocorrect), "page": page, "limit": limit}
        payload = await LastFmConnect.request("artist.getTopTracks", params)
        container = section(payload, "toptracks") if payload else None
        if container is None:
            return None
        return attr_page(container, map_items(container, "track", _map_track))

    @staticmethod
    async def get_top_tags(artist: str | None, mbid: str | None, autocorrect: bool) -> list[Tag] | None:
        payload = await LastFmConnect.request("artist.getTopTags", _identity(artist, mbid, autocorrect))
        container = section(payload, "toptags") if payload else None
        if container is None:
            return None
        return map_items(container, "tag", map_tag)

    @staticmethod
    async def get_user_tags(artist: str | None, mbid: str | None, user: str, autocorrect: bool) -> list[Tag] | None:
        payload = await LastFmConnect.request("artist.getTags", {**_identity(artist, mbid, autocorrect), "user": user})
        container = section(payload, "tags") if payload else None
        if container is None:
            return None
        return map_items(container, "tag", map_tag)

    @staticmethod
    async def get_correction(artist: str) -> ArtistCorrection | None:
        payload = await LastFmConnect.request("artist.getCorrection", {"artist": artist})
        corrections = section(payload, "corrections") if payload else None
        if corrections is None:
            return None
        correction = corrections.get("correction")
        if isinstance(correction, list):
            correction = correction[0] if correction else None
        if not isinstance(correction, dict) or not isinstance(correction.get("artist"), dict):
            return None
        raw = correction["artist"]
        attr = correction.get("@attr")
        return ArtistCorrection(
            name=raw.get("name", artist),
            corrected=isinstance(attr, dict) and attr.get("artistcorrected") == "1",
            mbid=non_empty(raw.get("mbid")),
            url=non_empty(raw.get("url")),
        )

    @staticmethod
    async def search(artist: str, page: int, limit: int) -> Page[ArtistRef]:
        payload = await LastFmConnect.request("artist.search", {"artist": artist, "page": page, "limit": limit})
        results = section(payload, "results") if payload else None
        if results is None:
            return Page(items=[], page=page, total_pages=1, total=0)
        return search_page(results, map_items(results.get("artistmatches"), "artist", map_artist_ref))
