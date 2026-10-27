from dataclasses import replace

from mcp_servers.lastfm_mcp.data.gateway.artist_gateway import ArtistGateway
from mcp_servers.lastfm_mcp.data.model.lastfm_model import ArtistCorrection
from mcp_servers.lastfm_mcp.service.lastfm_input import (
    DEFAULT_LIMIT,
    artist_identity,
    normalize_lang,
    normalize_limit,
    normalize_page,
    normalize_text,
    normalize_username,
)
from mcp_servers.lastfm_mcp.service.lastfm_operation import lastfm_operation


class ArtistService:
    @staticmethod
    @lastfm_operation
    async def get_info(
        artist: str | None = None,
        mbid: str | None = None,
        lang: str | None = None,
        username: str | None = None,
        autocorrect: bool = True,
        full_bio: bool = False,
    ):
        name, mbid = artist_identity(artist, mbid)
        info = await ArtistGateway.get_info(name, mbid, normalize_lang(lang), normalize_username(username), autocorrect)
        if info is None or full_bio:
            return info
        return replace(info, content=None)

    @staticmethod
    @lastfm_operation
    async def get_similar(
        artist: str | None = None, mbid: str | None = None, limit: int = DEFAULT_LIMIT, autocorrect: bool = True
    ):
        name, mbid = artist_identity(artist, mbid)
        return await ArtistGateway.get_similar(name, mbid, normalize_limit(limit), autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_top_albums(
        artist: str | None = None,
        mbid: str | None = None,
        page: int = 1,
        limit: int = DEFAULT_LIMIT,
        autocorrect: bool = True,
    ):
        name, mbid = artist_identity(artist, mbid)
        return await ArtistGateway.get_top_albums(name, mbid, normalize_page(page), normalize_limit(limit), autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_top_tracks(
        artist: str | None = None,
        mbid: str | None = None,
        page: int = 1,
        limit: int = DEFAULT_LIMIT,
        autocorrect: bool = True,
    ):
        name, mbid = artist_identity(artist, mbid)
        return await ArtistGateway.get_top_tracks(name, mbid, normalize_page(page), normalize_limit(limit), autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_top_tags(artist: str | None = None, mbid: str | None = None, autocorrect: bool = True):
        name, mbid = artist_identity(artist, mbid)
        return await ArtistGateway.get_top_tags(name, mbid, autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_user_tags(
        user: str, artist: str | None = None, mbid: str | None = None, autocorrect: bool = True
    ):
        name, mbid = artist_identity(artist, mbid)
        return await ArtistGateway.get_user_tags(name, mbid, normalize_username(user, required=True), autocorrect)

    @staticmethod
    @lastfm_operation
    async def get_correction(artist: str):
        name = normalize_text(artist, "artist", required=True)
        correction = await ArtistGateway.get_correction(name)
        # Sem correção conhecida não é um erro: o nome pesquisado fica como está.
        return correction or ArtistCorrection(name=name, corrected=False)

    @staticmethod
    @lastfm_operation
    async def search(artist: str, page: int = 1, limit: int = DEFAULT_LIMIT):
        name = normalize_text(artist, "artist", required=True)
        return await ArtistGateway.search(name, normalize_page(page), normalize_limit(limit))
