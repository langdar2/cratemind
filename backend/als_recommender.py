"""ALS-based track recommender for CrateMind.

Uses implicit's AlternatingLeastSquares for item-item similarity (seed-track
mode) and user-score prediction (no-seed mode).  Falls back to play_count
sorting when the model is absent or training has not yet run.

Track identity
--------------
Training operates on dicts (from library_cache) whose ID field is
``gerbera_id`` (int) or ``id`` (int).  The model stores IDs as strings.
At ranking time the caller may pass either plain dicts (same fields) or
Track Pydantic models whose ``rating_key`` attribute is the string form of
gerbera_id.  Both shapes are handled transparently.
"""

import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "data" / "als_model.pkl"
MIN_PLAYS_FOR_TRAINING = 5


def _track_id(track: Any) -> str:
    """Extract the canonical string ID from a Track model or a cache dict."""
    if hasattr(track, "rating_key"):
        return str(track.rating_key)
    return str(track.get("gerbera_id") or track.get("id") or "")


def _play_count(track: Any) -> int:
    if hasattr(track, "play_count"):
        return int(track.play_count or 0)
    return int(track.get("play_count") or 0)


class _RestrictedUnpickler(pickle.Unpickler):
    """Only allow unpickling ALS model objects — blocks arbitrary code execution."""
    _ALLOWED_MODULES = frozenset({
        "implicit.als", "implicit.cpu.als", "implicit.gpu.als",
        "numpy", "numpy.core.multiarray", "numpy._core.multiarray",
        "scipy.sparse", "scipy.sparse._csr", "scipy.sparse._csc",
        "builtins", "collections",
    })

    def find_class(self, module: str, name: str):
        if module in self._ALLOWED_MODULES:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Blocked unpickling from untrusted module: {module}.{name}"
        )


class ALSRecommender:
    """Lightweight ALS wrapper with safe fallback."""

    def __init__(self) -> None:
        self._model: Any = None
        self._item_ids: list[str] = []
        self._item_id_to_idx: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls) -> "ALSRecommender":
        """Return a new instance, restoring a previously saved model if found."""
        inst = cls()
        try:
            with MODEL_PATH.open("rb") as fh:
                data = _RestrictedUnpickler(fh).load()
            if not isinstance(data, dict) or "model" not in data or "item_ids" not in data:
                raise ValueError("Invalid ALS model format")
            inst._model = data["model"]
            inst._item_ids = data["item_ids"]
            inst._item_id_to_idx = {tid: i for i, tid in enumerate(inst._item_ids)}
            logger.info(
                "ALS model loaded from %s (%d items)", MODEL_PATH, len(inst._item_ids)
            )
        except FileNotFoundError:
            pass  # No saved model yet
        except Exception as exc:  # corrupt pickle, version mismatch, …
            logger.warning("Could not load ALS model: %s", exc)
        return inst

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, tracks: list[dict]) -> bool:
        """Build a user-item matrix from play_count and fit the ALS model.

        Returns True on success, False when preconditions are not met (implicit
        not installed, too few played tracks) or training fails.

        Saves the model to MODEL_PATH on success.
        """
        try:
            import implicit  # noqa: PLC0415
            import scipy.sparse as sp  # noqa: PLC0415
        except ImportError:
            logger.warning(
                "implicit / scipy not installed — ALS training skipped. "
                "Run: pip install implicit scipy"
            )
            return False

        played = [t for t in tracks if _play_count(t) > 0]
        if len(played) < MIN_PLAYS_FOR_TRAINING:
            logger.info(
                "ALS: only %d tracks with play_count > 0 (need %d) — skipping training",
                len(played),
                MIN_PLAYS_FOR_TRAINING,
            )
            return False

        try:
            item_ids = [
                str(t.get("gerbera_id") or t.get("id") or str(i))
                for i, t in enumerate(tracks)
            ]
            n_items = len(item_ids)

            # Single implicit user (index 0) whose confidence equals play_count
            rows, cols, data = [], [], []
            for idx, t in enumerate(tracks):
                pc = _play_count(t)
                if pc > 0:
                    rows.append(0)
                    cols.append(idx)
                    data.append(float(pc))

            matrix = sp.csr_matrix((data, (rows, cols)), shape=(1, n_items))

            model = implicit.als.AlternatingLeastSquares(
                factors=64, iterations=20, regularization=0.1
            )
            model.fit(matrix)

            self._model = model
            self._item_ids = item_ids
            self._item_id_to_idx = {tid: i for i, tid in enumerate(item_ids)}

            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with MODEL_PATH.open("wb") as fh:
                pickle.dump({"model": model, "item_ids": item_ids}, fh)

            logger.info("ALS model trained and saved (%d items)", n_items)
            return True

        except Exception as exc:
            logger.warning("ALS training failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank(
        self,
        candidate_tracks: list,
        seed_track_id: str | None = None,
        n: int = 50,
    ) -> list:
        """Return up to *n* candidate tracks ordered by ALS relevance score.

        When *seed_track_id* is given and known to the model, uses item-to-item
        cosine similarity against that seed.  Otherwise uses the dot product of
        the single user's latent vector with each item vector.

        Falls back to descending play_count order if the model is not ready or
        an error occurs.
        """
        if self._model is None:
            logger.info(
                "ALS: no model loaded — falling back to play_count sort (%d candidates → top %d)",
                len(candidate_tracks), n,
            )
            return self._fallback_rank(candidate_tracks, n)

        try:
            return self._als_rank(candidate_tracks, seed_track_id, n)
        except Exception as exc:
            logger.warning("ALS ranking failed (%s) — falling back to play_count sort", exc)
            return self._fallback_rank(candidate_tracks, n)

    def _fallback_rank(self, tracks: list, n: int) -> list:
        """Sort descending by play_count, return up to *n* tracks."""
        return sorted(tracks, key=_play_count, reverse=True)[:n]

    def _als_rank(
        self, tracks: list, seed_track_id: str | None, n: int
    ) -> list:
        import numpy as np  # noqa: PLC0415

        item_factors = self._model.item_factors  # shape (n_items, factors)

        if seed_track_id and seed_track_id in self._item_id_to_idx:
            seed_idx = self._item_id_to_idx[seed_track_id]
            ref_vec = item_factors[seed_idx]
            logger.info(
                "ALS: item-to-item ranking (seed=%s, model=%d items, candidates=%d → top %d)",
                seed_track_id, len(self._item_ids), len(tracks), n,
            )
        else:
            ref_vec = self._model.user_factors[0]  # user 0
            logger.info(
                "ALS: user-preference ranking (model=%d items, candidates=%d → top %d)",
                len(self._item_ids), len(tracks), n,
            )

        # Score: (als_score_or_-inf, play_count) — both sorted descending.
        # Known tracks: ALS dot-product score (always > -inf).
        # Unknown tracks: -inf so they always rank below known tracks,
        #                 then sorted by play_count descending as tiebreaker.
        scored: list[tuple[float, int, Any]] = []
        for track in tracks:
            tid = _track_id(track)
            if tid in self._item_id_to_idx:
                idx = self._item_id_to_idx[tid]
                score = float(np.dot(ref_vec, item_factors[idx]))
            else:
                score = float("-inf")
            scored.append((score, _play_count(track), track))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [t for _, _, t in scored[:n]]


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once at import time
# ---------------------------------------------------------------------------

recommender = ALSRecommender.load()
