"""Tests for playlist generation."""

import json
from unittest.mock import MagicMock, patch


def _parse_sse_events(generator):
    """Parse SSE events from generate_playlist_stream into (event, data) tuples."""
    events = []
    for raw in generator:
        if raw.startswith(":"):
            continue  # SSE comment (heartbeat)
        for line in raw.strip().split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                events.append((event_type, json.loads(line[len("data: "):])))
    return events


class TestPlaylistGeneration:
    """Tests for playlist generation (streaming)."""

    def test_generate_validates_tracks_against_library(self, mocker, mock_plex_tracks):
        """Generated playlist should only contain tracks from library."""
        from backend.generator import generate_playlist_stream
        from backend.llm_client import LLMResponse

        # Convert Track fixtures to cache-dict format expected by _cached_track_to_model
        cached_tracks = [
            {"rating_key": t.rating_key, "title": t.title, "artist": t.artist,
             "album": t.album, "duration_ms": t.duration_ms, "year": t.year,
             "genres": t.genres, "play_count": 0}
            for t in mock_plex_tracks[:5]
        ]

        mock_response = LLMResponse(
            content=json.dumps([
                {"artist": "Radiohead", "album": "The Bends", "title": "Fake Plastic Trees"},
                {"artist": "Pearl Jam", "album": "Ten", "title": "Black"},
            ]),
            input_tokens=1000,
            output_tokens=100,
            model="test-model"
        )

        with patch("backend.generator.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.generate.return_value = mock_response
            mock_client.analyze.return_value = LLMResponse(
                content='{"title": "Test", "narrative": "Test narrative."}',
                input_tokens=100, output_tokens=50, model="test-model"
            )
            mock_client.parse_json_response.side_effect = [
                json.loads(mock_response.content),
                {"title": "Test", "narrative": "Test narrative."},
            ]
            mock_llm.return_value = mock_client

            with patch("backend.generator.library_cache.has_cached_tracks", return_value=True):
                with patch("backend.generator.library_cache.get_tracks_by_filters", return_value=cached_tracks):
                    with patch("backend.generator.library_cache.save_result", return_value="abc123"):
                        events = _parse_sse_events(generate_playlist_stream(
                            prompt="90s alternative",
                            genres=["Alternative", "Rock"],
                            decades=["1990s"],
                            track_count=25,
                            exclude_live=True,
                        ))

                        # Collect track rating keys from track batch events
                        track_keys = []
                        for etype, data in events:
                            if etype == "tracks":
                                track_keys.extend(t["rating_key"] for t in data["batch"])

                        library_keys = {t.rating_key for t in mock_plex_tracks}
                        for key in track_keys:
                            assert key in library_keys

    def test_generate_handles_empty_filter_results(self, mocker):
        """Should emit error event when no tracks match filters."""
        from backend.generator import generate_playlist_stream

        with patch("backend.generator.get_llm_client") as mock_llm:
            mock_llm.return_value = MagicMock()

            with patch("backend.generator.library_cache.has_cached_tracks", return_value=True):
                with patch("backend.generator.library_cache.get_tracks_by_filters", return_value=[]):
                    events = _parse_sse_events(generate_playlist_stream(
                        prompt="nonexistent genre",
                        genres=["Nonexistent"],
                        decades=["1800s"],
                        track_count=25,
                        exclude_live=True,
                    ))

                    error_events = [d for t, d in events if t == "error"]
                    assert len(error_events) == 1
                    assert "No tracks" in error_events[0]["message"]

    def test_fuzzy_matching_finds_similar_titles(self, mocker, mock_plex_tracks):
        """Should fuzzy match LLM responses to library tracks."""
        from backend.generator import generate_playlist_stream
        from backend.llm_client import LLMResponse

        # Convert Track fixtures to cache-dict format expected by _cached_track_to_model
        cached_tracks = [
            {"rating_key": t.rating_key, "title": t.title, "artist": t.artist,
             "album": t.album, "duration_ms": t.duration_ms, "year": t.year,
             "genres": t.genres, "play_count": 0}
            for t in mock_plex_tracks[:5]
        ]

        mock_response = LLMResponse(
            content=json.dumps([
                {"artist": "Radiohead", "album": "The Bends", "title": "Fake Plastic Tree"},
            ]),
            input_tokens=1000,
            output_tokens=100,
            model="test-model"
        )

        with patch("backend.generator.get_llm_client") as mock_llm:
            mock_client = MagicMock()
            mock_client.generate.return_value = mock_response
            mock_client.analyze.return_value = LLMResponse(
                content='{"title": "Test", "narrative": "Test."}',
                input_tokens=100, output_tokens=50, model="test-model"
            )
            mock_client.parse_json_response.side_effect = [
                json.loads(mock_response.content),
                {"title": "Test", "narrative": "Test."},
            ]
            mock_llm.return_value = mock_client

            with patch("backend.generator.library_cache.has_cached_tracks", return_value=True):
                with patch("backend.generator.library_cache.get_tracks_by_filters", return_value=cached_tracks):
                    with patch("backend.generator.library_cache.save_result", return_value="abc123"):
                        events = _parse_sse_events(generate_playlist_stream(
                            prompt="radiohead",
                            genres=["Alternative"],
                            decades=["1990s"],
                            track_count=25,
                            exclude_live=True,
                        ))

                        # Should complete without error
                        error_events = [d for t, d in events if t == "error"]
                        assert len(error_events) == 0


class TestTrackMatching:
    """Tests for track matching utilities."""

    def test_simplify_string_removes_punctuation(self):
        """Should remove punctuation from strings."""
        from backend.generator import simplify_string

        assert simplify_string("Don't Stop") == "dont stop"
        assert simplify_string("Rock & Roll") == "rock  roll"
        assert simplify_string("(Remastered)") == "remastered"

    def test_simplify_string_normalizes_unicode(self):
        """Should normalize unicode characters."""
        from backend.generator import simplify_string

        assert simplify_string("Café") == "cafe"
        assert simplify_string("Motörhead") == "motorhead"

    def test_normalize_artist_handles_and_variations(self):
        """Should handle 'and' vs '&' variations."""
        from backend.generator import normalize_artist

        variations = normalize_artist("Simon & Garfunkel")
        assert "Simon & Garfunkel" in variations
        assert "Simon and Garfunkel" in variations

        variations = normalize_artist("Tom and Jerry")
        assert "Tom and Jerry" in variations
        assert "Tom & Jerry" in variations

class TestNarrativeGeneration:
    """Tests for curator narrative generation."""

    def test_generate_narrative_returns_title_and_narrative(self, mocker):
        """Should generate creative title and narrative from track selections."""
        from backend.generator import generate_narrative
        from backend.llm_client import LLMResponse

        track_selections = [
            {"artist": "Radiohead", "title": "Fake Plastic Trees", "reason": "Melancholic atmosphere"},
            {"artist": "Pearl Jam", "title": "Black", "reason": "Emotional depth"},
        ]

        mock_response = LLMResponse(
            content='{"title": "Rainstorm Reverie", "narrative": "This playlist weaves through Radiohead\'s Fake Plastic Trees and Pearl Jam\'s Black for a moody journey."}',
            input_tokens=500,
            output_tokens=50,
            model="test-model"
        )

        mock_client = MagicMock()
        mock_client.generate.return_value = mock_response
        mock_client.parse_json_response.return_value = {
            "title": "Rainstorm Reverie",
            "narrative": "This playlist weaves through Radiohead's Fake Plastic Trees and Pearl Jam's Black for a moody journey."
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert "Rainstorm Reverie" in title
        # Title should include date suffix
        assert " - " in title
        assert "Fake Plastic Trees" in narrative or len(narrative) > 0

    def test_generate_narrative_fallback_on_failure(self, mocker):
        """Should return fallback title on LLM failure."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.generate.side_effect = Exception("LLM error")

        title, narrative = generate_narrative(track_selections, mock_client)

        # Should return fallback title with date
        assert "Playlist" in title
        assert narrative == ""

    def test_generate_narrative_passes_through_long_narrative(self, mocker):
        """Should pass through narrative without truncation (LLM prompt guides length)."""
        from backend.generator import generate_narrative
        from backend.llm_client import LLMResponse

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        long_narrative = "A" * 600
        mock_response = LLMResponse(
            content=json.dumps({"title": "Test", "narrative": long_narrative}),
            input_tokens=500,
            output_tokens=50,
            model="test-model"
        )

        mock_client = MagicMock()
        mock_client.generate.return_value = mock_response
        mock_client.parse_json_response.return_value = {
            "title": "Test",
            "narrative": long_narrative
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        # No truncation - LLM prompt guides length instead
        assert narrative == long_narrative

    def test_generate_narrative_handles_array_wrapped_response(self, mocker):
        """Should handle array-wrapped JSON responses from some LLMs."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        # Some LLMs wrap their response in an array like [{...}]
        mock_client.parse_json_response.return_value = [
            {"title": "Wrapped Title", "narrative": "This is wrapped in an array."}
        ]

        title, narrative = generate_narrative(track_selections, mock_client)

        assert "Wrapped Title" in title
        assert narrative == "This is wrapped in an array."

    def test_generate_narrative_handles_alternate_key_names(self, mocker):
        """Should try alternate keys like description, text, content."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        # LLM uses "description" instead of "narrative"
        mock_client.parse_json_response.return_value = {
            "title": "Alt Key Test",
            "description": "Using description key instead of narrative."
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert "Alt Key Test" in title
        assert narrative == "Using description key instead of narrative."

    def test_generate_narrative_handles_text_key(self, mocker):
        """Should fall back to 'text' key for narrative."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.parse_json_response.return_value = {
            "title": "Text Key Test",
            "text": "Using text key."
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert narrative == "Using text key."

    def test_generate_narrative_handles_content_key(self, mocker):
        """Should fall back to 'content' key for narrative."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.parse_json_response.return_value = {
            "title": "Content Key Test",
            "content": "Using content key."
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert narrative == "Using content key."

    def test_generate_narrative_empty_array_returns_fallback(self, mocker):
        """Should handle empty array response gracefully."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.parse_json_response.return_value = []

        title, narrative = generate_narrative(track_selections, mock_client)

        # Should return fallback
        assert "Playlist" in title
        assert narrative == ""

    def test_generate_narrative_prefers_narrative_key_over_alternatives(self, mocker):
        """Should prefer 'narrative' key when multiple keys present."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.parse_json_response.return_value = {
            "title": "Priority Test",
            "narrative": "Primary value",
            "description": "Should not use this"
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert narrative == "Primary value"

    def test_generate_narrative_empty_string_uses_fallback_key(self, mocker):
        """Should try alternate keys when narrative key is empty string."""
        from backend.generator import generate_narrative

        track_selections = [{"artist": "Test", "title": "Song", "reason": "Test"}]

        mock_client = MagicMock()
        mock_client.parse_json_response.return_value = {
            "title": "Empty Primary Test",
            "narrative": "",
            "description": "Fallback description used"
        }

        title, narrative = generate_narrative(track_selections, mock_client)

        assert narrative == "Fallback description used"


class TestLiveVersionFiltering:
    """Tests for live version detection."""

    def test_is_live_version_detects_live_keyword(self):
        """Should detect 'live' in track or album title."""
        from backend.generator import is_live_version

        class MockTrack:
            def __init__(self, title, album_title):
                self.title = title
                self._album_title = album_title

            def album(self):
                return MagicMock(title=self._album_title)

        assert is_live_version(MockTrack("Song - Live", "Album")) is True
        assert is_live_version(MockTrack("Song", "Live at Madison Square Garden")) is True
        assert is_live_version(MockTrack("Song", "Album")) is False

    def test_is_live_version_detects_concert_keyword(self):
        """Should detect 'concert' in track or album title."""
        from backend.generator import is_live_version

        class MockTrack:
            def __init__(self, title, album_title):
                self.title = title
                self._album_title = album_title

            def album(self):
                return MagicMock(title=self._album_title)

        assert is_live_version(MockTrack("Song", "Concert Recording")) is True

    def test_is_live_version_detects_date_patterns(self):
        """Should detect date patterns in album titles."""
        from backend.generator import is_live_version

        class MockTrack:
            def __init__(self, title, album_title):
                self.title = title
                self._album_title = album_title

            def album(self):
                return MagicMock(title=self._album_title)

        assert is_live_version(MockTrack("Song", "2023-05-15 Show")) is True
        assert is_live_version(MockTrack("Song", "1999/12/31 New Years")) is True
        assert is_live_version(MockTrack("Song", "Regular Album 2023")) is False


class TestPlayedUnplayedSplit:
    """Tests for the 70/30 played/unplayed track selection."""

    def _make_tracks(self, n_played: int, n_unplayed: int) -> list:
        from backend.models import Track
        played = [
            Track(rating_key=str(i), title=f"Played {i}", artist=f"A{i}",
                  album="Album", duration_ms=180000, year=2000,
                  genres=[], art_url="", play_count=i + 1)
            for i in range(n_played)
        ]
        unplayed = [
            Track(rating_key=str(n_played + i), title=f"Unplayed {i}", artist=f"B{i}",
                  album="Album", duration_ms=180000, year=2000,
                  genres=[], art_url="", play_count=0)
            for i in range(n_unplayed)
        ]
        return played + unplayed

    def test_split_returns_70_percent_played(self):
        from backend.generator import _apply_played_unplayed_split
        tracks = self._make_tracks(n_played=100, n_unplayed=100)
        result = _apply_played_unplayed_split(tracks, target=20)
        played = [t for t in result if t.play_count > 0]
        unplayed = [t for t in result if t.play_count == 0]
        assert len(result) == 20
        assert len(played) == 14  # round(20 * 0.7)
        assert len(unplayed) == 6

    def test_split_preserves_input_order(self):
        from backend.generator import _apply_played_unplayed_split
        tracks = self._make_tracks(n_played=50, n_unplayed=50)
        result = _apply_played_unplayed_split(tracks, target=10)
        # Result should be a subset preserving relative order from input
        input_keys = [t.rating_key for t in tracks]
        result_keys = [t.rating_key for t in result]
        result_positions = [input_keys.index(k) for k in result_keys]
        assert result_positions == sorted(result_positions)

    def test_split_fills_shortfall_from_other_bucket(self):
        from backend.generator import _apply_played_unplayed_split
        # Only 3 unplayed tracks, need 6 → shortfall filled from played
        tracks = self._make_tracks(n_played=50, n_unplayed=3)
        result = _apply_played_unplayed_split(tracks, target=20)
        assert len(result) == 20

    def test_split_passthrough_when_below_target(self):
        from backend.generator import _apply_played_unplayed_split
        tracks = self._make_tracks(n_played=5, n_unplayed=5)
        result = _apply_played_unplayed_split(tracks, target=20)
        assert len(result) == 10  # all 10 returned unchanged
