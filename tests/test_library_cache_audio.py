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


from backend.models import AudioConstraints


def _insert_track(conn, gerbera_id, bpm=None, energy=None, acousticness=None, **kwargs):
    """Helper: insert a minimal track row."""
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, bpm, energy, acousticness) "
        "VALUES (?, ?, ?, ?, '[]', '/f.mp3', ?, ?, ?)",
        (gerbera_id, kwargs.get("title", "T"), kwargs.get("artist", "A"), kwargs.get("album", "B"),
         bpm, energy, acousticness),
    )
    conn.commit()


def test_get_tracks_by_filters_bpm_constraint(conn):
    """Audio constraint bpm_max filters extracted tracks; NULL tracks always pass."""
    _insert_track(conn, 1, bpm=150.0, energy=0.5, acousticness=0.5)  # too fast
    _insert_track(conn, 2, bpm=90.0, energy=0.5, acousticness=0.5)   # fits
    _insert_track(conn, 3)  # no extraction yet → always included

    from backend import library_cache
    constraints = AudioConstraints(bpm_max=100)
    result = library_cache.get_tracks_by_filters(audio_constraints=constraints)
    ids = {r["gerbera_id"] for r in result}
    assert 1 not in ids    # filtered out (bpm 150 > 100)
    assert 2 in ids        # passes
    assert 3 in ids        # NULL → always included


def test_get_tracks_by_filters_energy_constraint(conn):
    """energy_max filters tracks above threshold; NULL tracks pass."""
    _insert_track(conn, 1, bpm=90.0, energy=0.8, acousticness=0.5)  # too loud
    _insert_track(conn, 2, bpm=90.0, energy=0.3, acousticness=0.5)  # quiet enough
    _insert_track(conn, 3)

    from backend import library_cache
    constraints = AudioConstraints(energy_max=0.5)
    result = library_cache.get_tracks_by_filters(audio_constraints=constraints)
    ids = {r["gerbera_id"] for r in result}
    assert 1 not in ids
    assert 2 in ids
    assert 3 in ids


def test_get_tracks_by_filters_acousticness_constraint(conn):
    """acousticness_min filters electric tracks; NULL tracks pass."""
    _insert_track(conn, 1, bpm=90.0, energy=0.3, acousticness=0.2)  # electric
    _insert_track(conn, 2, bpm=90.0, energy=0.3, acousticness=0.8)  # acoustic
    _insert_track(conn, 3)

    from backend import library_cache
    constraints = AudioConstraints(acousticness_min=0.6)
    result = library_cache.get_tracks_by_filters(audio_constraints=constraints)
    ids = {r["gerbera_id"] for r in result}
    assert 1 not in ids
    assert 2 in ids
    assert 3 in ids


def test_count_tracks_by_filters_with_audio_constraints(conn):
    """count_tracks_by_filters respects audio_constraints."""
    _insert_track(conn, 1, bpm=150.0, energy=0.5, acousticness=0.5)
    _insert_track(conn, 2, bpm=90.0, energy=0.5, acousticness=0.5)
    _insert_track(conn, 3)  # NULL

    from backend import library_cache
    constraints = AudioConstraints(bpm_max=100)
    count = library_cache.count_tracks_by_filters(audio_constraints=constraints)
    assert count == 2  # track 2 + track 3 (NULL)


def test_get_tracks_by_filters_bpm_min_constraint(conn):
    """bpm_min filters tracks below threshold; NULL tracks always pass."""
    _insert_track(conn, 1, bpm=60.0, energy=0.5, acousticness=0.5)   # too slow
    _insert_track(conn, 2, bpm=130.0, energy=0.5, acousticness=0.5)  # fast enough
    _insert_track(conn, 3)  # NULL → always included

    from backend import library_cache
    constraints = AudioConstraints(bpm_min=80)
    result = library_cache.get_tracks_by_filters(audio_constraints=constraints)
    ids = {r["gerbera_id"] for r in result}
    assert 1 not in ids    # filtered out (bpm 60 < 80)
    assert 2 in ids        # passes
    assert 3 in ids        # NULL → always included


def test_count_tracks_by_filters_genre_and_audio_constraints(conn):
    """count_tracks_by_filters with genres AND audio_constraints both applied."""
    # Track 1: matching genre but bpm too high → excluded by audio
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, bpm) "
        "VALUES (1, 'T', 'A', 'B', '[\"Rock\"]', '/a.mp3', 150.0)"
    )
    # Track 2: matching genre, bpm ok → included
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, bpm) "
        "VALUES (2, 'T', 'A', 'B', '[\"Rock\"]', '/b.mp3', 90.0)"
    )
    # Track 3: wrong genre → excluded by genre filter
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path, bpm) "
        "VALUES (3, 'T', 'A', 'B', '[\"Jazz\"]', '/c.mp3', 90.0)"
    )
    # Track 4: matching genre, bpm IS NULL → included (graceful degradation)
    conn.execute(
        "INSERT INTO tracks (gerbera_id, title, artist, album, genres, file_path) "
        "VALUES (4, 'T', 'A', 'B', '[\"Rock\"]', '/d.mp3')"
    )
    conn.commit()

    from backend import library_cache
    constraints = AudioConstraints(bpm_max=100)
    count = library_cache.count_tracks_by_filters(genres=["Rock"], audio_constraints=constraints)
    assert count == 2  # track 2 (bpm ok) + track 4 (bpm NULL)
