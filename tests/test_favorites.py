"""Tests for favorites DB loading and is_favorite helper."""
import os
import sqlite3
import tempfile

import pytest

from backend.favorites import is_favorite, Favorites


def make_favorites_db(artists=None, albums=None):
    """Create a temp favorites DB and return (conn, db_path)."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE favorites (
            type TEXT NOT NULL, artist TEXT NOT NULL,
            album TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );
    """)
    for a in (artists or []):
        conn.execute("INSERT INTO favorites (type, artist, album) VALUES ('artist', ?, '')", (a,))
    for artist, album in (albums or []):
        conn.execute("INSERT INTO favorites (type, artist, album) VALUES ('album', ?, ?)", (artist, album))
    conn.commit()
    return conn, db_path


def test_is_favorite_artist(monkeypatch):
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db(artists=["Miles Davis", "Nick Cave"])
    try:
        monkeypatch.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
        favs = load_favorites()
        assert is_favorite(favs, "Miles Davis") is True
        assert is_favorite(favs, "miles davis") is True   # case-insensitive
        assert is_favorite(favs, "Bob Dylan") is False
    finally:
        conn.close()
        os.unlink(db_path)


def test_is_favorite_album(monkeypatch):
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db(albums=[("Tom Waits", "Rain Dogs")])
    try:
        monkeypatch.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
        favs = load_favorites()
        assert is_favorite(favs, "Tom Waits", "Rain Dogs") is True
        assert is_favorite(favs, "Tom Waits", "Bone Machine") is False
    finally:
        conn.close()
        os.unlink(db_path)


def test_empty_db_returns_empty_favorites(monkeypatch):
    from backend.favorites import load_favorites
    conn, db_path = make_favorites_db()
    try:
        monkeypatch.setattr("backend.library_cache.ensure_db_initialized", lambda: conn)
        favs = load_favorites()
        assert is_favorite(favs, "Anyone") is False
    finally:
        conn.close()
        os.unlink(db_path)
