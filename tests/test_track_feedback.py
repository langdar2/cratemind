import pytest
from backend import library_cache


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point library_cache at a fresh temp database for each test."""
    db = tmp_path / "test.db"
    monkeypatch.setattr(library_cache, "DB_PATH", db)
    conn = library_cache.get_db_connection()
    library_cache.init_schema(conn)
    conn.close()
    yield


def test_save_and_get_feedback():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    fb = library_cache.get_track_feedback()
    assert len(fb) == 1
    assert fb[0]["gerbera_id"] == 1
    assert fb[0]["rating"] == 1


def test_dislike_overwrites_like():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", -1)
    fb = library_cache.get_track_feedback()
    assert len(fb) == 1
    assert fb[0]["rating"] == -1


def test_toggle_off_removes_rating():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 0)
    assert library_cache.get_track_feedback() == []


def test_multiple_tracks():
    library_cache.save_track_feedback(1, "Song A", "Artist A", "Album A", 1)
    library_cache.save_track_feedback(2, "Song B", "Artist B", "Album B", -1)
    fb = library_cache.get_track_feedback()
    ratings = {r["gerbera_id"]: r["rating"] for r in fb}
    assert ratings[1] == 1
    assert ratings[2] == -1


def test_get_feedback_empty():
    assert library_cache.get_track_feedback() == []
