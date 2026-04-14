"""Tests for audio_constraints flowing through the generation pipeline."""
from unittest.mock import patch, MagicMock
from backend.models import AudioConstraints


def test_get_tracks_from_cache_passes_audio_constraints():
    """_get_tracks_from_cache passes audio_constraints to get_tracks_by_filters."""
    constraints = AudioConstraints(bpm_max=100, energy_max=0.4)

    with patch("backend.generator.library_cache.has_cached_tracks", return_value=True), \
         patch("backend.generator.library_cache.get_tracks_by_filters", return_value=[]) as mock_get:
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
