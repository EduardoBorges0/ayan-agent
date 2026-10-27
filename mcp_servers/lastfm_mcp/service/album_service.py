from dataclasses import replace

from mcp_servers.lastfm_mcp.data.gateway.album_gateway import AlbumGateway
from mcp_servers.lastfm_mcp.service.lastfm_input import (
    DEFAULT_LIMIT,
    album_identity,
    normalize_lang,
    normalize_limit,
    normalize_page,
    normalize_text,
    normalize_username,
)
from mcp_servers.lastfm_mcp.service.lastfm_operation import lastfm_operation


class AlbumService:
    @staticmethod
    @lastfm_operation
    async def get_info(
        artist: str | None = None,
        album: str | None = None,
        mbid: str | None = None,
        lang: str | None = None,
        username: str | None = None,
        autocorrect: bool = True,
        full_wiki: bool = False,
    ):
        artist, album, mbid = album_identity(artist, album, mbid)
        info = await AlbumGateway.get_info(
            artist, album, mbid, normalize_lang(lang), normalize_username(username), autocorrect
        )
        if info is None or full_wiki:
            return info
        return replace(info, content=None)

    @staticmethod
    @lastfm_operation
    async def get_top_tags(
        artist: str | None = None, album: str | None = None, mbid: str | None = None, autocorrect: bool = True
    ):
        artist, album, mbid = album_identity(artist, album, mbid)
        return await AlbumGateway.get_top_tags(artist, album, mbid, autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_user_tags(
        user: str,
        artist: str | None = None,
        album: str | None = None,
        mbid: str | None = None,
        autocorrect: bool = True,
    ):
        artist, album, mbid = album_identity(artist, album, mbid)
        return await AlbumGateway.get_user_tags(
            artist, album, mbid, normalize_username(user, required=True), autocorrect
        )

    @staticmethod
    @lastfm_operation
    async def search(album: str, page: int = 1, limit: int = DEFAULT_LIMIT):
        name = normalize_text(album, "album", required=True)
        return await AlbumGateway.search(name, normalize_page(page), normalize_limit(limit))
