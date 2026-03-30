import json
from backend.generator import build_track_prompt_entry
from backend.favorites import Favorites

def test_favorite_artist_gets_tag():
    favs = Favorites(artists={"miles davis"}, albums=set())
    entry = build_track_prompt_entry(
        track={"title": "So What", "artist": "Miles Davis", "album": "Kind of Blue",
               "genres": '["Jazz"]', "year": 1959, "play_count": 5},
        favs=favs,
    )
    assert "[FAVORITE]" in entry

def test_non_favorite_has_no_tag():
    favs = Favorites(artists=set(), albums=set())
    entry = build_track_prompt_entry(
        track={"title": "Track", "artist": "Unknown", "album": "Album",
               "genres": "[]", "year": 2000, "play_count": 0},
        favs=favs,
    )
    assert "[FAVORITE]" not in entry

def test_entry_contains_key_fields():
    favs = Favorites(artists=set(), albums=set())
    entry = build_track_prompt_entry(
        track={"title": "So What", "artist": "Miles Davis", "album": "Kind of Blue",
               "genres": '["Jazz"]', "year": 1959, "play_count": 5},
        favs=favs,
    )
    assert "Miles Davis" in entry
    assert "So What" in entry
    assert "1959" in entry
    assert "Jazz" in entry
    assert "5" in entry  # play_count
