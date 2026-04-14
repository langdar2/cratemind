"""Tests for audio feature extraction module."""
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from backend.audio_features import extract_features_for_file, AUDIO_LOAD_DURATION


def test_extract_features_returns_all_keys(tmp_path):
    """extract_features_for_file returns dict with all 5 feature keys."""
    sr = 22050
    y = np.zeros(sr * 5, dtype=np.float32)  # 5 seconds of silence

    with patch("backend.audio_features.librosa.load", return_value=(y, sr)):
        result = extract_features_for_file("/fake/path.mp3")

    assert set(result.keys()) == {"bpm", "energy", "spectral_centroid", "zero_crossing_rate", "acousticness"}
    for v in result.values():
        assert isinstance(v, float)


def test_extract_features_bpm_range():
    """BPM should be a positive float."""
    sr = 22050
    y = np.random.rand(sr * 10).astype(np.float32)

    with patch("backend.audio_features.librosa.load", return_value=(y, sr)):
        result = extract_features_for_file("/fake/path.mp3")

    assert result["bpm"] > 0


def test_extract_features_energy_range():
    """Energy (RMS) should be between 0 and 1."""
    sr = 22050
    y = np.ones(sr * 5, dtype=np.float32) * 0.5  # constant amplitude

    with patch("backend.audio_features.librosa.load", return_value=(y, sr)):
        result = extract_features_for_file("/fake/path.mp3")

    assert 0.0 <= result["energy"] <= 1.0


def test_extract_features_acousticness_range():
    """Acousticness should be between 0 and 1."""
    sr = 22050
    y = np.random.rand(sr * 5).astype(np.float32)

    with patch("backend.audio_features.librosa.load", return_value=(y, sr)):
        result = extract_features_for_file("/fake/path.mp3")

    assert 0.0 <= result["acousticness"] <= 1.0


def test_extract_features_load_duration():
    """librosa.load is called with the configured duration limit."""
    sr = 22050
    y = np.zeros(sr * AUDIO_LOAD_DURATION, dtype=np.float32)

    with patch("backend.audio_features.librosa.load", return_value=(y, sr)) as mock_load:
        extract_features_for_file("/fake/path.mp3")
        mock_load.assert_called_once_with("/fake/path.mp3", duration=AUDIO_LOAD_DURATION, mono=True)
