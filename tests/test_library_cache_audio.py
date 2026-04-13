"""Tests for audio feature DB functions."""
import sqlite3
import pytest
from backend import library_cache


@pytest.fixture
def conn(tmp_path):
    """Fresh in-memory DB with schema initialized."""
    import backend.library_cache as lc
    # Patch DB_PATH so ensure_db_initialized uses tmp dir
    original = lc.DB_PATH
    lc.DB_PATH = tmp_path / "test.db"
    lc._schema_initialized = False
    conn = lc.ensure_db_initialized()
    yield conn
    conn.close()
    lc.DB_PATH = original
    lc._schema_initialized = False


def test_audio_columns_exist(conn):
    """Schema migration adds all 6 audio columns to tracks table."""
    cursor = conn.execute("PRAGMA table_info(tracks)")
    cols = {row[1] for row in cursor.fetchall()}
    for col in ("bpm", "energy", "spectral_centroid", "zero_crossing_rate", "acousticness", "audio_extracted_at"):
        assert col in cols, f"Missing column: {col}"


def test_sync_state_audio_columns_exist(conn):
    """Schema migration adds audio extraction progress columns to sync_state."""
    cursor = conn.execute("PRAGMA table_info(sync_state)")
    cols = {row[1] for row in cursor.fetchall()}
    assert "audio_extraction_current" in cols
    assert "audio_extraction_total" in cols


def test_get_tracks_without_audio_features_empty(conn):
    """Returns empty list when no tracks exist."""
    result = library_cache.get_tracks_without_audio_features()
    assert result == []


def test_save_and_get_audio_features(conn):
    """save_audio_features writes values; audio_extracted_at is set."""
    # Insert a track
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path) "
        "VALUES (1, 'Test', 'Artist', 'Album', '[]', '/music/test.mp3')"
    )
    conn.commit()

    library_cache.save_audio_features(1, {
        "bpm": 92.4,
        "energy": 0.31,
        "spectral_centroid": 2341.0,
        "zero_crossing_rate": 0.08,
        "acousticness": 0.74,
    })

    row = conn.execute(
        "SELECT bpm, energy, spectral_centroid, zero_crossing_rate, acousticness, audio_extracted_at "
        "FROM tracks WHERE gerbera_id = 1"
    ).fetchone()
    assert abs(row[0] - 92.4) < 0.01
    assert abs(row[1] - 0.31) < 0.001
    assert row[5] is not None  # audio_extracted_at set


def test_get_tracks_without_audio_features_filters_extracted(conn):
    """Only returns tracks where bpm IS NULL."""
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, bpm) "
        "VALUES (1, 'T1', 'A', 'B', '[]', '/a.mp3', 90.0)"
    )
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path) "
        "VALUES (2, 'T2', 'A', 'B', '[]', '/b.mp3')"
    )
    conn.commit()

    result = library_cache.get_tracks_without_audio_features()
    assert len(result) == 1
    assert result[0]["gerbera_id"] == 2


def test_get_audio_extraction_state(conn):
    state = library_cache.get_audio_extraction_state()
    assert "current" in state
    assert "total" in state
    assert "is_extracting" in state
