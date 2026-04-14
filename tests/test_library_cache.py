import sqlite3
import pytest
import tempfile
import os
from backend.library_cache import init_db, sync_tracks, get_tracks
from backend.gerbera_client import GerberaTrack


def make_track(**kwargs) -> GerberaTrack:
    defaults = dict(
        gerbera_id=1, title="So What", artist="Miles Davis",
        album="Kind of Blue", genre="Jazz", year=1959,
        duration_ms=562000, file_path="/music/so_what.flac", play_count=5
    )
    defaults.update(kwargs)
    return GerberaTrack(**defaults)


def test_init_db_creates_schema():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        cursor = conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "title" in columns
        assert "artist" in columns
        assert "file_path" in columns
        assert "play_count" in columns
        assert "gerbera_id" in columns
        assert "user_rating" not in columns
        assert "rating_key" not in columns
    finally:
        conn.close()
        os.unlink(db_path)


def test_sync_tracks_inserts_records():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        tracks = [make_track(), make_track(gerbera_id=2, title="Blue in Green")]
        sync_tracks(conn, tracks)
        cursor = conn.execute("SELECT COUNT(*) FROM tracks")
        assert cursor.fetchone()[0] == 2
    finally:
        conn.close()
        os.unlink(db_path)


def test_sync_tracks_upserts_on_conflict():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [make_track(play_count=3)])
        sync_tracks(conn, [make_track(play_count=7)])  # same gerbera_id=1
        cursor = conn.execute("SELECT play_count FROM tracks WHERE gerbera_id = 1")
        assert cursor.fetchone()[0] == 7
        cursor = conn.execute("SELECT COUNT(*) FROM tracks")
        assert cursor.fetchone()[0] == 1
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_tracks_filter_by_genre():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, genre="Jazz"),
            make_track(gerbera_id=2, genre="Rock"),
        ])
        results = get_tracks(conn, genres=["Jazz"])
        assert len(results) == 1
        assert results[0]["artist"] == "Miles Davis"
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_tracks_filter_by_min_play_count():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, play_count=10),
            make_track(gerbera_id=2, play_count=1),
        ])
        results = get_tracks(conn, min_play_count=5)
        assert len(results) == 1
        assert results[0]["play_count"] == 10
    finally:
        conn.close()
        os.unlink(db_path)


def test_is_live_detection():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, title="Normal Track"),
            make_track(gerbera_id=2, title="Concert in Berlin"),
        ])
        results = get_tracks(conn, exclude_live=True)
        assert len(results) == 1
        assert results[0]["title"] == "Normal Track"
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_tracks_filter_by_year_range():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, year=1959),
            make_track(gerbera_id=2, year=1975),
            make_track(gerbera_id=3, year=1990),
        ])
        results = get_tracks(conn, min_year=1970, max_year=1980)
        assert len(results) == 1
        assert results[0]["year"] == 1975
    finally:
        conn.close()
        os.unlink(db_path)


def test_is_live_detected_from_album():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, title="Normal Track", album="Live at Fillmore"),
            make_track(gerbera_id=2, title="Another Track", album="Studio Album"),
        ])
        results = get_tracks(conn, exclude_live=True)
        assert len(results) == 1
        assert results[0]["album"] == "Studio Album"
    finally:
        conn.close()
        os.unlink(db_path)


def test_min_year_zero_is_respected():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        sync_tracks(conn, [
            make_track(gerbera_id=1, year=0),
            make_track(gerbera_id=2, year=1975),
            make_track(gerbera_id=3, year=1990),
        ])
        results = get_tracks(conn, min_year=0, max_year=1980)
        assert len(results) == 2
        assert any(r["year"] == 0 for r in results)
        assert any(r["year"] == 1975 for r in results)
    finally:
        conn.close()
        os.unlink(db_path)


def test_init_db_creates_favorites_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        conn = init_db(db_path)
        cursor = conn.execute("PRAGMA table_info(favorites)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "type" in columns
        assert "artist" in columns
        assert "album" in columns
        assert "created_at" in columns
    finally:
        conn.close()
        os.unlink(db_path)


def make_db_with_favorites():
    """Create a temp DB with both tracks and favorites tables."""
    import tempfile, os
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = f.name
    f.close()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gerbera_id INTEGER UNIQUE NOT NULL,
            title TEXT NOT NULL, artist TEXT, album TEXT,
            genres TEXT, year INTEGER, duration_ms INTEGER,
            file_path TEXT, play_count INTEGER DEFAULT 0,
            is_live BOOLEAN DEFAULT 0,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bpm REAL
        );
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_sync_at TIMESTAMP,
            track_count INTEGER DEFAULT 0
        );
        INSERT OR IGNORE INTO sync_state (id) VALUES (1);
        CREATE TABLE IF NOT EXISTS favorites (
            type TEXT NOT NULL, artist TEXT NOT NULL,
            album TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );
    """)
    conn.commit()
    return conn, db_path


def test_toggle_favorite_insert_then_remove():
    from backend.library_cache import toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        # First toggle: inserts → returns True
        result = toggle_favorite("artist", "Radiohead", conn=conn)
        assert result is True
        row = conn.execute("SELECT * FROM favorites WHERE artist='Radiohead'").fetchone()
        assert row is not None

        # Second toggle: removes → returns False
        result = toggle_favorite("artist", "Radiohead", conn=conn)
        assert result is False
        row = conn.execute("SELECT * FROM favorites WHERE artist='Radiohead'").fetchone()
        assert row is None
    finally:
        conn.close()
        os.unlink(db_path)


def test_toggle_favorite_album():
    from backend.library_cache import toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        result = toggle_favorite("album", "Radiohead", album="OK Computer", conn=conn)
        assert result is True
        row = conn.execute(
            "SELECT * FROM favorites WHERE artist='Radiohead' AND album='OK Computer'"
        ).fetchone()
        assert row is not None
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_artists_with_stats_returns_sorted_by_track_count():
    from backend.library_cache import get_artists_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        # Insert tracks: Miles Davis 3 tracks, Radiohead 1 track
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (?,?,?,?,?,?,?)",
            [
                (1, "So What", "Miles Davis", "Kind of Blue", "[]", "/a.flac", 0),
                (2, "All Blues", "Miles Davis", "Kind of Blue", "[]", "/b.flac", 0),
                (3, "Blue in Green", "Miles Davis", "Kind of Blue", "[]", "/c.flac", 0),
                (4, "Creep", "Radiohead", "Pablo Honey", "[]", "/d.flac", 0),
            ],
        )
        conn.commit()
        rows = get_artists_with_stats(conn=conn)
        assert rows[0]["artist"] == "Miles Davis"
        assert rows[0]["track_count"] == 3
        assert rows[1]["artist"] == "Radiohead"
        assert rows[1]["track_count"] == 1
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_artists_with_stats_is_favorite_flag():
    from backend.library_cache import get_artists_with_stats, toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        conn.execute(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (1,'Creep','Radiohead','Pablo Honey','[]','/d.flac',0)"
        )
        conn.commit()
        toggle_favorite("artist", "Radiohead", conn=conn)
        rows = get_artists_with_stats(conn=conn)
        assert rows[0]["is_favorite"] is True
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_albums_with_stats_returns_sorted_by_track_count():
    from backend.library_cache import get_albums_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (?,?,?,?,?,?,?)",
            [
                (1, "Track1", "Radiohead", "OK Computer", "[]", "/a.flac", 0),
                (2, "Track2", "Radiohead", "OK Computer", "[]", "/b.flac", 0),
                (3, "Creep",  "Radiohead", "Pablo Honey", "[]", "/c.flac", 0),
            ],
        )
        conn.commit()
        rows = get_albums_with_stats(conn=conn)
        assert rows[0]["album"] == "OK Computer"
        assert rows[0]["track_count"] == 2
        assert rows[1]["album"] == "Pablo Honey"
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_albums_with_stats_is_favorite_flag():
    from backend.library_cache import get_albums_with_stats, toggle_favorite
    conn, db_path = make_db_with_favorites()
    try:
        conn.execute(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live) VALUES (1,'Track1','Radiohead','OK Computer','[]','/a.flac',0)"
        )
        conn.commit()
        toggle_favorite("album", "Radiohead", album="OK Computer", conn=conn)
        rows = get_albums_with_stats(conn=conn)
        assert rows[0]["is_favorite"] is True
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_artists_with_stats_audio_extracted_count():
    from backend.library_cache import get_artists_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live, bpm) VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "So What",    "Miles Davis", "Kind of Blue", "[]", "/a.flac", 0, 120.0),
                (2, "All Blues",  "Miles Davis", "Kind of Blue", "[]", "/b.flac", 0, None),
                (3, "Creep",      "Radiohead",   "Pablo Honey",  "[]", "/c.flac", 0, None),
            ],
        )
        conn.commit()
        rows = get_artists_with_stats(conn=conn)
        miles = next(r for r in rows if r["artist"] == "Miles Davis")
        radiohead = next(r for r in rows if r["artist"] == "Radiohead")
        assert miles["audio_extracted"] == 1
        assert radiohead["audio_extracted"] == 0
    finally:
        conn.close()
        os.unlink(db_path)


def test_get_albums_with_stats_audio_extracted_count():
    from backend.library_cache import get_albums_with_stats
    conn, db_path = make_db_with_favorites()
    try:
        conn.executemany(
            "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, is_live, bpm) VALUES (?,?,?,?,?,?,?,?)",
            [
                (1, "Track1", "Radiohead", "OK Computer", "[]", "/a.flac", 0, 95.0),
                (2, "Track2", "Radiohead", "OK Computer", "[]", "/b.flac", 0, 102.0),
                (3, "Creep",  "Radiohead", "Pablo Honey",  "[]", "/c.flac", 0, None),
            ],
        )
        conn.commit()
        rows = get_albums_with_stats(conn=conn)
        ok = next(r for r in rows if r["album"] == "OK Computer")
        pablo = next(r for r in rows if r["album"] == "Pablo Honey")
        assert ok["audio_extracted"] == 2
        assert pablo["audio_extracted"] == 0
    finally:
        conn.close()
        os.unlink(db_path)
