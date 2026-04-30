# backend/audio_ranker.py
"""Content-based track ranker using audio feature cosine similarity.

Each track is represented as a normalized 5D feature vector:
  [bpm, energy, spectral_centroid, zero_crossing_rate, acousticness]

Seed mode: ranks candidates by cosine similarity to the seed track's vector.
Constraint mode: ranks by similarity to a centroid built from AudioConstraints.
No seed + no constraints: random shuffle.
Tracks with missing audio features rank below all scored tracks, sorted
alphabetically by title within that group.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from backend.models import AudioConstraints

logger = logging.getLogger(__name__)

# Normalization reference ranges: (min, max) per feature
_FEATURE_RANGES: dict[str, tuple[float, float]] = {
    "bpm":                (0.0, 250.0),
    "energy":             (0.0, 1.0),
    "spectral_centroid":  (0.0, 8000.0),
    "zero_crossing_rate": (0.0, 0.5),
    "acousticness":       (0.0, 1.0),
}
_FEATURE_KEYS = list(_FEATURE_RANGES.keys())


def _normalize(value: float, min_val: float, max_val: float) -> float:
    if max_val == min_val:
        return 0.5
    return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))


def _feature_vector(track: Any) -> np.ndarray | None:
    """Extract and normalize audio features into a unit-range vector.

    Returns None if any feature is NULL — caller treats this as unscored.
    Accepts both Track Pydantic models (attribute access) and cache dicts.
    """
    values: list[float] = []
    for key in _FEATURE_KEYS:
        val = getattr(track, key, None) if hasattr(track, key) else track.get(key)
        if val is None:
            return None
        lo, hi = _FEATURE_RANGES[key]
        values.append(_normalize(float(val), lo, hi))
    return np.array(values, dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _track_id(track: Any) -> str:
    if hasattr(track, "rating_key"):
        return str(track.rating_key)
    if isinstance(track, dict):
        return str(track.get("gerbera_id") or track.get("id") or "")
    return ""


def _constraints_to_vector(constraints: AudioConstraints) -> np.ndarray:
    """Build a reference vector from AudioConstraints midpoints.

    For each constrained field, the midpoint of the allowed range is used.
    Unconstrained fields default to the center (0.5 after normalization).
    """
    bpm_lo = constraints.bpm_min or 0.0
    bpm_hi = constraints.bpm_max or 250.0
    bpm_mid = (bpm_lo + bpm_hi) / 2.0

    energy_hi = constraints.energy_max if constraints.energy_max is not None else 1.0
    energy_mid = energy_hi / 2.0

    spectral_mid = 4000.0   # center of [0, 8000]
    zcr_mid = 0.25          # center of [0, 0.5]

    acousticness_lo = constraints.acousticness_min if constraints.acousticness_min is not None else 0.0
    acousticness_mid = (acousticness_lo + 1.0) / 2.0

    raw = {
        "bpm": bpm_mid,
        "energy": energy_mid,
        "spectral_centroid": spectral_mid,
        "zero_crossing_rate": zcr_mid,
        "acousticness": acousticness_mid,
    }
    values = [_normalize(raw[k], *_FEATURE_RANGES[k]) for k in _FEATURE_KEYS]
    return np.array(values, dtype=np.float32)


def _track_title(track: Any) -> str:
    if hasattr(track, "title"):
        return (track.title or "").lower()
    return (track.get("title") or "").lower() if isinstance(track, dict) else ""


class AudioFeatureRanker:
    """Ranks candidate tracks by sonic similarity using cosine distance on audio feature vectors."""

    def rank(
        self,
        candidate_tracks: list,
        seed_track_id: str | None = None,
        audio_constraints: AudioConstraints | None = None,
        n: int = 50,
    ) -> list:
        """Return up to *n* candidate tracks ordered by sonic similarity.

        Priority:
        1. Seed track mode — cosine similarity to seed's feature vector.
        2. Constraint centroid mode — cosine similarity to AudioConstraints midpoint.
        3. No reference — random shuffle.

        Tracks without audio features sink below all scored tracks and are
        sorted alphabetically by title within that group.
        """
        ref_vec = self._reference_vector(candidate_tracks, seed_track_id, audio_constraints)

        if ref_vec is None:
            result = list(candidate_tracks)
            random.shuffle(result)
            return result[:n]

        scored: list[tuple[float, Any]] = []
        unscored: list[Any] = []
        for track in candidate_tracks:
            vec = _feature_vector(track)
            if vec is None:
                unscored.append(track)
            else:
                scored.append((_cosine_similarity(ref_vec, vec), track))

        scored.sort(key=lambda x: x[0], reverse=True)
        unscored.sort(key=_track_title)

        ranked = [t for _, t in scored]
        return (ranked + unscored)[:n]

    def _reference_vector(
        self,
        candidate_tracks: list,
        seed_track_id: str | None,
        audio_constraints: AudioConstraints | None,
    ) -> np.ndarray | None:
        if seed_track_id:
            for track in candidate_tracks:
                if _track_id(track) == seed_track_id:
                    vec = _feature_vector(track)
                    if vec is not None:
                        logger.info(
                            "AudioRanker: seed-track mode (seed=%s, candidates=%d)",
                            seed_track_id, len(candidate_tracks),
                        )
                        return vec
            logger.info(
                "AudioRanker: seed %s not found or has no features — falling back to constraints",
                seed_track_id,
            )

        if audio_constraints is not None:
            logger.info(
                "AudioRanker: constraint-centroid mode (candidates=%d)",
                len(candidate_tracks),
            )
            return _constraints_to_vector(audio_constraints)

        logger.info(
            "AudioRanker: no seed or constraints — random shuffle (candidates=%d)",
            len(candidate_tracks),
        )
        return None


# Module-level singleton — used by generator.py
ranker = AudioFeatureRanker()
