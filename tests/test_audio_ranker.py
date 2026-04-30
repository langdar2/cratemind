# tests/test_audio_ranker.py
"""Tests for AudioFeatureRanker."""

import pytest

from backend.audio_ranker import AudioFeatureRanker, _feature_vector, _constraints_to_vector
from backend.models import AudioConstraints


def _make_track(gerbera_id: int, bpm: float = None, energy: float = None,
                spectral_centroid: float = None, zero_crossing_rate: float = None,
                acousticness: float = None, title: str = None) -> dict:
    return {
        "gerbera_id": gerbera_id,
        "title": title or f"Track {gerbera_id}",
        "artist": f"Artist {gerbera_id}",
        "album": "Album",
        "bpm": bpm,
        "energy": energy,
        "spectral_centroid": spectral_centroid,
        "zero_crossing_rate": zero_crossing_rate,
        "acousticness": acousticness,
    }


def _full_track(gerbera_id: int, **kwargs) -> dict:
    defaults = {
        "bpm": 120.0, "energy": 0.5, "spectral_centroid": 3000.0,
        "zero_crossing_rate": 0.1, "acousticness": 0.5,
    }
    defaults.update(kwargs)
    return _make_track(gerbera_id, **defaults)


class TestFeatureVector:
    def test_returns_none_when_any_feature_missing(self):
        track = _make_track(1, bpm=120.0, energy=0.5)  # spectral_centroid etc. are None
        assert _feature_vector(track) is None

    def test_returns_array_when_all_features_present(self):
        track = _full_track(1)
        vec = _feature_vector(track)
        assert vec is not None
        assert vec.shape == (5,)
        assert all(0.0 <= v <= 1.0 for v in vec)

    def test_bpm_normalized_to_half_at_midpoint(self):
        track = _full_track(1, bpm=125.0)  # midpoint of 0–250
        vec = _feature_vector(track)
        assert abs(vec[0] - 0.5) < 0.01


class TestConstraintsToVector:
    def test_energy_max_maps_to_midpoint_of_allowed_range(self):
        constraints = AudioConstraints(energy_max=0.3)
        vec = _constraints_to_vector(constraints)
        # midpoint of [0, 0.3] = 0.15; energy range is [0,1] so normalized = 0.15
        assert abs(vec[1] - 0.15) < 0.01

    def test_acousticness_min_maps_to_midpoint_of_allowed_range(self):
        constraints = AudioConstraints(acousticness_min=0.7)
        vec = _constraints_to_vector(constraints)
        # midpoint of [0.7, 1.0] = 0.85; acousticness range is [0,1] so normalized = 0.85
        assert abs(vec[4] - 0.85) < 0.01

    def test_unconstrained_energy_defaults_to_center(self):
        constraints = AudioConstraints()
        vec = _constraints_to_vector(constraints)
        assert abs(vec[1] - 0.5) < 0.01


class TestSeedMode:
    def test_seed_track_ranked_first(self):
        seed = _full_track(1, bpm=60.0, energy=0.1, acousticness=0.9)
        others = [_full_track(i, bpm=200.0, energy=0.9, acousticness=0.1) for i in range(2, 10)]

        ranker = AudioFeatureRanker()
        result = ranker.rank([seed] + others, seed_track_id="1", n=10)

        assert result[0]["gerbera_id"] == 1

    def test_sonically_similar_track_ranks_above_dissimilar(self):
        seed = _full_track(1, bpm=80.0, energy=0.2, acousticness=0.8)
        similar = _full_track(2, bpm=85.0, energy=0.25, acousticness=0.75)
        dissimilar = _full_track(3, bpm=200.0, energy=0.9, acousticness=0.1)

        ranker = AudioFeatureRanker()
        result = ranker.rank([seed, similar, dissimilar], seed_track_id="1", n=3)

        ids = [t["gerbera_id"] for t in result]
        assert ids.index(2) < ids.index(3)

    def test_unknown_seed_falls_back_to_constraints(self):
        constraints = AudioConstraints(energy_max=0.3)
        quiet = _full_track(1, energy=0.1)
        loud = _full_track(2, energy=0.9)

        ranker = AudioFeatureRanker()
        result = ranker.rank(
            [loud, quiet],
            seed_track_id="nonexistent-99",
            audio_constraints=constraints,
            n=2,
        )
        assert result[0]["gerbera_id"] == 1


class TestConstraintCentroidMode:
    def test_low_energy_constraint_ranks_quiet_track_first(self):
        constraints = AudioConstraints(energy_max=0.3)
        quiet = _full_track(1, energy=0.1)
        loud = _full_track(2, energy=0.9)

        ranker = AudioFeatureRanker()
        result = ranker.rank([loud, quiet], audio_constraints=constraints, n=2)

        assert result[0]["gerbera_id"] == 1

    def test_no_seed_no_constraints_returns_n_tracks(self):
        tracks = [_full_track(i) for i in range(20)]
        ranker = AudioFeatureRanker()
        result = ranker.rank(tracks, n=10)
        assert len(result) == 10


class TestTracksWithoutFeatures:
    def test_tracks_without_features_sorted_to_end(self):
        scored = _full_track(1)
        unscored = _make_track(2)  # all audio features None

        ranker = AudioFeatureRanker()
        result = ranker.rank([unscored, scored], audio_constraints=AudioConstraints(), n=2)

        assert result[0]["gerbera_id"] == 1

    def test_unscored_tracks_sorted_alphabetically_by_title(self):
        tracks = [
            _make_track(i, title=title)
            for i, title in enumerate(["Zebra", "Apple", "Mango"])
        ]
        ranker = AudioFeatureRanker()
        result = ranker.rank(tracks, audio_constraints=AudioConstraints(), n=3)

        titles = [t["title"] for t in result]
        assert titles == ["Apple", "Mango", "Zebra"]


class TestNParameter:
    def test_n_caps_result_length(self):
        tracks = [_full_track(i) for i in range(50)]
        ranker = AudioFeatureRanker()
        result = ranker.rank(tracks, audio_constraints=AudioConstraints(energy_max=0.5), n=10)
        assert len(result) <= 10

    def test_fewer_tracks_than_n_returns_all(self):
        tracks = [_full_track(i) for i in range(5)]
        ranker = AudioFeatureRanker()
        result = ranker.rank(tracks, audio_constraints=AudioConstraints(), n=50)
        assert len(result) == 5
