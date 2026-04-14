"""Tests for audio constraint extraction in analyzer.py."""
import pytest
from unittest.mock import patch, MagicMock
from backend.models import AudioConstraints


def _make_llm_client(data: dict):
    """Build a mock LLM client that returns `data` as parsed JSON."""
    mock_response = MagicMock()
    mock_response.total_tokens = 100
    mock_response.estimated_cost.return_value = 0.001

    mock_client = MagicMock()
    mock_client.analyze.return_value = mock_response
    mock_client.parse_json_response.return_value = data
    return mock_client


def test_analyze_prompt_no_audio_hints():
    """Prompt without acoustic hints → audio_constraints is None."""
    mock_client = _make_llm_client({
        "genres": ["Rock"],
        "decades": ["1990s"],
        "reasoning": "Generic rock playlist",
        "audio_constraints": None,
    })

    with patch("backend.analyzer.get_llm_client", return_value=mock_client), \
         patch("backend.analyzer.library_cache.get_cached_genre_decade_stats",
               return_value={"genres": [], "decades": []}):
        from backend.analyzer import analyze_prompt
        result = analyze_prompt("Play me some 90s rock")

    assert result.audio_constraints is None


def test_analyze_prompt_with_bpm_constraints():
    """Prompt with tempo hint → audio_constraints populated."""
    mock_client = _make_llm_client({
        "genres": ["Ambient"],
        "decades": [],
        "reasoning": "Slow ambient",
        "audio_constraints": {"bpm_min": 40, "bpm_max": 80, "energy_max": 0.3},
    })

    with patch("backend.analyzer.get_llm_client", return_value=mock_client), \
         patch("backend.analyzer.library_cache.get_cached_genre_decade_stats",
               return_value={"genres": [], "decades": []}):
        from backend.analyzer import analyze_prompt
        result = analyze_prompt("Something slow and quiet")

    assert result.audio_constraints is not None
    assert result.audio_constraints.bpm_min == 40
    assert result.audio_constraints.bpm_max == 80
    assert result.audio_constraints.energy_max == 0.3
    assert result.audio_constraints.acousticness_min is None


def test_analyze_prompt_with_acousticness():
    """Prompt requesting acoustic/no-electric → acousticness_min set."""
    mock_client = _make_llm_client({
        "genres": ["Folk"],
        "decades": [],
        "reasoning": "Acoustic folk",
        "audio_constraints": {"acousticness_min": 0.7},
    })

    with patch("backend.analyzer.get_llm_client", return_value=mock_client), \
         patch("backend.analyzer.library_cache.get_cached_genre_decade_stats",
               return_value={"genres": [], "decades": []}):
        from backend.analyzer import analyze_prompt
        result = analyze_prompt("Acoustic guitar, no electric instruments")

    assert result.audio_constraints.acousticness_min == 0.7


def test_analyze_prompt_empty_audio_constraints_dict():
    """LLM returning {} for audio_constraints → None (not a vacuous object)."""
    mock_client = _make_llm_client({
        "genres": ["Electronic"],
        "decades": [],
        "reasoning": "Electronic music",
        "audio_constraints": {},
    })

    with patch("backend.analyzer.get_llm_client", return_value=mock_client), \
         patch("backend.analyzer.library_cache.get_cached_genre_decade_stats",
               return_value={"genres": [], "decades": []}):
        from backend.analyzer import analyze_prompt
        result = analyze_prompt("Electronic music")

    assert result.audio_constraints is None
