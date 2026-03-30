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
