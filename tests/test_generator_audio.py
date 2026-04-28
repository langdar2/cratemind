"""Tests for audio_constraints flowing through the generation pipeline."""
from unittest.mock import patch, MagicMock
from backend.models import AudioConstraints


def test_get_tracks_from_cache_passes_audio_constraints():
    """_get_tracks_from_cache passes audio_constraints to get_tracks_by_filters."""
    constraints = AudioConstraints(bpm_max=100, energy_max=0.4)

    # Return 50 tracks so the fallback is NOT triggered (pool is not too small)
    enough_tracks = [{"gerbera_id": i, "title": "T", "artist": "A", "album": "B",
                      "duration_ms": 200000, "year": 2000, "genres": [], "play_count": 0,
                      "is_live": 0, "file_path": "/f.mp3"} for i in range(50)]

    with patch("backend.generator.library_cache.has_cached_tracks", return_value=True), \
         patch("backend.generator.library_cache.get_tracks_by_filters",
               return_value=enough_tracks) as mock_get:
        from backend.generator import _get_tracks_from_cache
        _get_tracks_from_cache(
            genres=None, decades=None, exclude_live=True,
            min_rating=0, max_tracks_to_ai=500,
            audio_constraints=constraints,
        )
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["audio_constraints"] == constraints


def test_get_tracks_from_cache_no_constraints():
    """_get_tracks_from_cache passes None when no constraints given."""
    with patch("backend.generator.library_cache.has_cached_tracks", return_value=True), \
         patch("backend.generator.library_cache.get_tracks_by_filters", return_value=[]) as mock_get:
        from backend.generator import _get_tracks_from_cache
        _get_tracks_from_cache(
            genres=None, decades=None, exclude_live=True,
            min_rating=0, max_tracks_to_ai=500,
        )
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs.get("audio_constraints") is None


def test_audio_constraints_dropped_when_pool_too_small():
    """If audio-constrained pool < 50 tracks, retry without audio constraints."""
    constraints = AudioConstraints(bpm_max=60)  # very restrictive

    call_count = {"n": 0}

    def mock_get_tracks(**kwargs):
        call_count["n"] += 1
        if kwargs.get("audio_constraints") is not None:
            # First call: with constraints → tiny pool
            return [{"gerbera_id": i, "title": "T", "artist": "A", "album": "B",
                     "duration_ms": 200000, "year": 2000, "genres": [], "play_count": 0,
                     "is_live": 0, "file_path": "/f.mp3"} for i in range(3)]
        # Second call: without constraints → full pool
        return [{"gerbera_id": i, "title": "T", "artist": "A", "album": "B",
                 "duration_ms": 200000, "year": 2000, "genres": [], "play_count": 0,
                 "is_live": 0, "file_path": "/f.mp3"} for i in range(100)]

    with patch("backend.generator.library_cache.has_cached_tracks", return_value=True), \
         patch("backend.generator.library_cache.get_tracks_by_filters",
               side_effect=mock_get_tracks):
        from backend.generator import _get_tracks_from_cache
        result, audio_dropped = _get_tracks_from_cache(
            genres=None, decades=None, exclude_live=True,
            min_rating=0, max_tracks_to_ai=500,
            audio_constraints=constraints,
        )

    assert call_count["n"] == 2    # retried without constraints
    assert len(result) == 100
    assert audio_dropped is True
