"""Tests for AudioConstraints model and AnalyzePromptResponse extension."""
import pytest
from backend.models import AudioConstraints, AnalyzePromptResponse, GenreCount, DecadeCount


def test_audio_constraints_all_optional():
    c = AudioConstraints()
    assert c.bpm_min is None
    assert c.bpm_max is None
    assert c.energy_max is None
    assert c.acousticness_min is None


def test_audio_constraints_partial():
    c = AudioConstraints(bpm_min=60, bpm_max=120)
    assert c.bpm_min == 60
    assert c.bpm_max == 120
    assert c.energy_max is None


def test_analyze_prompt_response_without_constraints():
    r = AnalyzePromptResponse(
        suggested_genres=[], suggested_decades=[],
        available_genres=[], available_decades=[],
        reasoning="test",
    )
    assert r.audio_constraints is None


def test_analyze_prompt_response_with_constraints():
    r = AnalyzePromptResponse(
        suggested_genres=[], suggested_decades=[],
        available_genres=[], available_decades=[],
        reasoning="test",
        audio_constraints=AudioConstraints(bpm_max=100, energy_max=0.4),
    )
    assert r.audio_constraints.bpm_max == 100
    assert r.audio_constraints.energy_max == 0.4
