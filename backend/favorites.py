import sqlite3
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Favorites:
    artists: set[str] = field(default_factory=set)   # lowercase artist names
    albums: set[tuple[str, str]] = field(default_factory=set)  # (artist_lower, album_lower)


def load_favorites() -> Favorites:
    """Load favorites from the SQLite library cache. Returns empty Favorites if table missing."""
    from backend import library_cache
    conn = library_cache.ensure_db_initialized()
    try:
        rows = conn.execute("SELECT type, artist, album FROM favorites").fetchall()
        artists = {r["artist"].lower() for r in rows if r["type"] == "artist"}
        albums = {(r["artist"].lower(), r["album"].lower()) for r in rows if r["type"] == "album"}
        return Favorites(artists=artists, albums=albums)
    except sqlite3.OperationalError:
        return Favorites()
    finally:
        conn.close()


def is_favorite(favs: Favorites, artist: str, album: Optional[str] = None) -> bool:
    """Return True if artist or artist+album is in favorites."""
    if artist.lower() in favs.artists:
        return True
    if album and (artist.lower(), album.lower()) in favs.albums:
        return True
    return False
