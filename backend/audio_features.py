"""Background audio feature extraction using librosa.

Extracts 5 acoustic features per track from the first AUDIO_LOAD_DURATION seconds:
  - bpm: tempo in BPM (beat_track)
  - energy: RMS loudness normalized to 0-1
  - spectral_centroid: average brightness in Hz
  - zero_crossing_rate: average ZCR (percussive vs. tonal proxy)
  - acousticness: harmonic/total energy ratio via HPSS (0=electric, 1=acoustic)
"""

import logging
import threading

import numpy as np
import librosa

from backend import library_cache

logger = logging.getLogger(__name__)

# Load only the first N seconds of each file for speed (~0.8s/track at 60s)
AUDIO_LOAD_DURATION = 60  # seconds


def extract_features_for_file(file_path: str) -> dict[str, float]:
    """Extract 5 audio features from a single audio file.

    Loads only the first AUDIO_LOAD_DURATION seconds for speed.

    Args:
        file_path: Absolute path to the audio file.

    Returns:
        Dict with keys: bpm, energy, spectral_centroid, zero_crossing_rate, acousticness.

    Raises:
        Exception: Re-raises any librosa/IO errors so the caller can skip + log.
    """
    y, sr = librosa.load(file_path, duration=AUDIO_LOAD_DURATION, mono=True)

    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])

    # Energy (RMS, clipped to 0-1)
    rms = float(np.sqrt(np.mean(y ** 2)))
    energy = min(1.0, max(0.0, rms))

    # Spectral centroid (mean across frames, in Hz)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    spectral_centroid = float(np.mean(centroid))

    # Zero crossing rate (mean across frames)
    zcr = librosa.feature.zero_crossing_rate(y)
    zero_crossing_rate = float(np.mean(zcr))

    # Acousticness via HPSS: ratio of harmonic energy to total energy
    y_harmonic, _ = librosa.effects.hpss(y)
    harmonic_energy = float(np.mean(y_harmonic ** 2))
    total_energy = float(np.mean(y ** 2))
    if total_energy > 0:
        acousticness = min(1.0, max(0.0, harmonic_energy / total_energy))
    else:
        acousticness = 0.0

    return {
        "bpm": bpm,
        "energy": energy,
        "spectral_centroid": spectral_centroid,
        "zero_crossing_rate": zero_crossing_rate,
        "acousticness": acousticness,
    }


def _run_extraction() -> None:
    """Extract audio features for all tracks with bpm IS NULL.

    Runs as a background daemon thread. Updates sync_state progress columns.
    Skips unreadable files and logs warnings without stopping.
    """
    library_cache._audio_extracting = True
    try:
        tracks = library_cache.get_tracks_without_audio_features()
        total = len(tracks)
        logger.info("Audio extraction started: %d tracks to process", total)

        # Write total to sync_state
        conn = library_cache.ensure_db_initialized()
        try:
            conn.execute(
                "UPDATE sync_state SET audio_extraction_current = 0, audio_extraction_total = ? WHERE id = 1",
                (total,),
            )
            conn.commit()
        finally:
            conn.close()

        for i, track in enumerate(tracks):
            gerbera_id = track["gerbera_id"]
            file_path = track["file_path"]
            try:
                features = extract_features_for_file(file_path)
                library_cache.save_audio_features(gerbera_id, features)
            except Exception as exc:
                logger.warning(
                    "Audio extraction failed for gerbera_id=%d path=%s: %s",
                    gerbera_id, file_path, exc,
                )

            # Update progress every 50 tracks
            if (i + 1) % 50 == 0 or (i + 1) == total:
                conn = library_cache.ensure_db_initialized()
                try:
                    conn.execute(
                        "UPDATE sync_state SET audio_extraction_current = ? WHERE id = 1",
                        (i + 1,),
                    )
                    conn.commit()
                finally:
                    conn.close()
                logger.info("Audio extraction progress: %d / %d", i + 1, total)

        logger.info("Audio extraction complete: %d tracks processed", total)
    finally:
        library_cache._audio_extracting = False


def extract_audio_features_background() -> None:
    """Start audio feature extraction as a background daemon thread.

    Safe to call after every sync. If extraction is already running,
    this call is a no-op.
    """
    if library_cache._audio_extracting:
        logger.info("Audio extraction already running — skipping start")
        return

    thread = threading.Thread(target=_run_extraction, daemon=True, name="audio-extractor")
    thread.start()
    logger.info("Audio extraction thread started")
