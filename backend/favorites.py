import yaml
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Favorites:
    artists: set[str] = field(default_factory=set)   # lowercase artist names
    albums: set[tuple[str, str]] = field(default_factory=set)  # (artist_lower, album_lower)


def load_favorites(path: str) -> Favorites:
    """Load favorites from a YAML file. Returns empty Favorites if file not found."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return Favorites()

    artists = {a.lower() for a in data.get("artists", [])}
    albums = {
        (entry["artist"].lower(), entry["album"].lower())
        for entry in data.get("albums", [])
    }
    return Favorites(artists=artists, albums=albums)


def is_favorite(favs: Favorites, artist: str, album: Optional[str] = None) -> bool:
    """Return True if artist or artist+album is in favorites."""
    if artist.lower() in favs.artists:
        return True
    if album and (artist.lower(), album.lower()) in favs.albums:
        return True
    return False
