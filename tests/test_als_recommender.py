"""Smoke tests for the ALS-based track recommender."""

import random
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.als_recommender import ALSRecommender


def _make_tracks(n: int = 200, seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    return [
        {
            "gerbera_id": i + 1,
            "title": f"Track {i}",
            "artist": f"Artist {i % 20}",
            "album": f"Album {i % 40}",
            "play_count": rng.randint(0, 50),
        }
        for i in range(n)
    ]


class TestALSRecommenderTrain:
    def test_train_returns_true_with_sufficient_data(self, tmp_path):
        """train() should succeed and persist a model file."""
        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als_model.pkl"):
            result = rec.train(tracks)

        assert result is True
        assert rec._model is not None
        assert len(rec._item_ids) == 200

    def test_train_returns_false_when_implicit_missing(self):
        """train() should return False gracefully when implicit is not installed."""
        import builtins

        original_import = builtins.__import__

        def _block_implicit(name, *args, **kwargs):
            if name in ("implicit", "scipy", "scipy.sparse"):
                raise ImportError(f"mocked missing: {name}")
            return original_import(name, *args, **kwargs)

        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("builtins.__import__", side_effect=_block_implicit):
            result = rec.train(tracks)

        assert result is False

    def test_train_returns_false_when_too_few_played_tracks(self):
        """train() should return False when fewer than MIN_PLAYS_FOR_TRAINING tracks have plays."""
        tracks = [
            {"gerbera_id": i, "title": f"T{i}", "play_count": 0}
            for i in range(100)
        ]
        # Give exactly MIN_PLAYS_FOR_TRAINING - 1 tracks a play count
        for i in range(4):
            tracks[i]["play_count"] = 1

        rec = ALSRecommender()
        result = rec.train(tracks)
        assert result is False


class TestALSRecommenderRank:
    def test_rank_returns_nonempty_list_of_tracks(self, tmp_path):
        """rank() should return a non-empty list of the same type passed in."""
        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als_model.pkl"):
            rec.train(tracks)

        result = rec.rank(candidate_tracks=tracks[:50], n=20)

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(t, dict) for t in result)

    def test_rank_respects_n_limit(self, tmp_path):
        """rank() should return at most n tracks."""
        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als_model.pkl"):
            rec.train(tracks)

        result = rec.rank(candidate_tracks=tracks, n=30)
        assert len(result) <= 30

    def test_rank_with_seed_track_id(self, tmp_path):
        """rank() with a seed_track_id should still return a valid list."""
        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als_model.pkl"):
            rec.train(tracks)

        seed_id = str(tracks[5]["gerbera_id"])
        result = rec.rank(candidate_tracks=tracks[:50], seed_track_id=seed_id, n=20)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_rank_with_unknown_seed_falls_back_to_user_score(self, tmp_path):
        """rank() with an unknown seed_track_id should not raise."""
        tracks = _make_tracks(200)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als_model.pkl"):
            rec.train(tracks)

        result = rec.rank(candidate_tracks=tracks[:50], seed_track_id="nonexistent-99999", n=20)
        assert isinstance(result, list)


class TestALSRecommenderFallback:
    def test_fallback_without_trained_model(self):
        """rank() on an untrained instance should fall back to play_count sort."""
        tracks = _make_tracks(50)
        rec = ALSRecommender()  # no train(), no load()

        result = rec.rank(candidate_tracks=tracks, n=20)

        assert isinstance(result, list)
        assert len(result) > 0
        # Fallback sorts by play_count descending
        play_counts = [t["play_count"] for t in result]
        assert play_counts == sorted(play_counts, reverse=True)

    def test_fallback_result_contains_dicts(self):
        """Fallback should return the original track dicts unchanged."""
        tracks = [{"gerbera_id": i, "play_count": i} for i in range(10)]
        rec = ALSRecommender()

        result = rec.rank(candidate_tracks=tracks, n=5)

        assert all("gerbera_id" in t for t in result)

    def test_load_returns_fresh_instance_when_no_file(self, tmp_path):
        """ALSRecommender.load() should return a fresh instance if no pickle exists."""
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "missing.pkl"):
            rec = ALSRecommender.load()

        assert rec._model is None
        assert rec._item_ids == []

    def test_load_restores_saved_model(self, tmp_path):
        """ALSRecommender.load() should restore a model saved by train()."""
        tracks = _make_tracks(100)
        model_path = tmp_path / "als_model.pkl"

        with patch("backend.als_recommender.MODEL_PATH", model_path):
            trainer = ALSRecommender()
            trainer.train(tracks)

            loader = ALSRecommender.load()

        assert loader._model is not None
        assert len(loader._item_ids) == 100


class TestALSUnknownTrackOrdering:
    """Unknown tracks (not in model) should be ordered by play_count."""

    def test_unknown_tracks_sorted_by_play_count(self, tmp_path):
        """Tracks unknown to the model should rank by play_count descending."""
        known_tracks = _make_tracks(100)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als.pkl"):
            rec.train(known_tracks)

        # Candidates are UNKNOWN tracks (ids 1000+) with varying play_counts
        unknown_tracks = [
            {"gerbera_id": 1000 + i, "title": f"Unknown{i}", "artist": f"X{i}",
             "album": "X", "play_count": pc}
            for i, pc in enumerate([5, 30, 0, 15, 1])
        ]

        result = rec.rank(candidate_tracks=unknown_tracks, n=5)
        play_counts = [t["play_count"] for t in result]
        assert play_counts == sorted(play_counts, reverse=True), (
            f"Unknown tracks not sorted by play_count: {play_counts}"
        )

    def test_known_tracks_rank_above_unknown_tracks(self, tmp_path):
        """Known (ALS-scored) tracks should always rank above unknown tracks."""
        known_tracks = _make_tracks(100)
        rec = ALSRecommender()
        with patch("backend.als_recommender.MODEL_PATH", tmp_path / "als.pkl"):
            rec.train(known_tracks)

        unknown_high_play = {"gerbera_id": 9999, "title": "PopularUnknown",
                             "artist": "Z", "album": "Z", "play_count": 9999}
        known_low_play = known_tracks[0].copy()  # has play_count from _make_tracks

        candidates = [unknown_high_play, known_low_play]
        result = rec.rank(candidate_tracks=candidates, n=2)

        # Known track must come first regardless of play_count
        first_id = str(result[0].get("gerbera_id") or result[0].get("id"))
        assert first_id == str(known_low_play["gerbera_id"])
