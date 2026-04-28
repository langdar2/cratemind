"""Tidal integration for track lookup via python-tidal (tidalapi).

Provides OAuth device-code login, session persistence, and track search
for matching missing library files to Tidal catalog entries.
"""

import logging
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
SESSION_FILE = DATA_DIR / "tidal-session.json"

# Module-level state
_session: Any = None
_login_future: Optional[Future] = None
_login_uri: Optional[str] = None
_lock = threading.Lock()


def _get_tidalapi():
    """Lazy import to avoid hard dependency."""
    try:
        import tidalapi
        return tidalapi
    except ImportError:
        raise RuntimeError(
            "tidalapi is not installed. Run: pip install tidalapi"
        )


def _ensure_session():
    """Create or return the cached tidalapi.Session."""
    global _session
    if _session is not None:
        return _session
    tidalapi = _get_tidalapi()
    _session = tidalapi.Session()
    return _session


def is_logged_in() -> bool:
    """Check whether a valid Tidal session exists."""
    try:
        session = _ensure_session()
        if SESSION_FILE.exists():
            session.load_session_from_file(SESSION_FILE)
        return session.check_login()
    except Exception:
        logger.debug("Tidal login check failed", exc_info=True)
        return False


def start_login() -> dict:
    """Initiate OAuth device-code login flow.

    Returns dict with 'verification_uri' and 'expires_in'.
    The caller should poll check_login_complete() until it returns True.
    """
    global _login_future, _login_uri
    with _lock:
        session = _ensure_session()
        login, future = session.login_oauth()
        _login_future = future
        _login_uri = f"https://{login.verification_uri_complete}"
        return {
            "verification_uri": _login_uri,
            "expires_in": login.expires_in,
        }


def check_login_complete() -> dict:
    """Check whether the OAuth login flow has completed.

    Returns dict with 'logged_in' bool and optional 'verification_uri'.
    """
    global _login_future, _login_uri
    with _lock:
        session = _ensure_session()

        # If future is done, save session
        if _login_future is not None and _login_future.done():
            try:
                _login_future.result()  # raises on error
            except Exception:
                logger.warning("Tidal OAuth login failed", exc_info=True)
                _login_future = None
                _login_uri = None
                return {"logged_in": False, "error": "Login fehlgeschlagen"}

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            session.save_session_to_file(SESSION_FILE)
            _login_future = None
            _login_uri = None
            return {"logged_in": True}

        # Check existing session
        if session.check_login():
            return {"logged_in": True}

        # Still waiting for user to authorize
        return {
            "logged_in": False,
            "verification_uri": _login_uri,
            "waiting": _login_future is not None,
        }


def logout() -> None:
    """Clear the Tidal session."""
    global _session, _login_future, _login_uri
    with _lock:
        _session = None
        _login_future = None
        _login_uri = None
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()


def search_track(artist: str, title: str) -> Optional[dict]:
    """Search Tidal for a track by artist and title.

    Returns dict with tidal_id and tidal_url, or None if not found.
    """
    try:
        tidalapi = _get_tidalapi()
        session = _ensure_session()
        if not session.check_login():
            return None

        query = f"{artist} {title}"
        results = session.search(query, models=[tidalapi.media.Track], limit=5)
        tracks = results.get("tracks", [])
        if not tracks:
            return None

        # Find best match (first result is usually best)
        best = tracks[0]
        return {
            "tidal_id": best.id,
            "tidal_url": f"https://tidal.com/browse/track/{best.id}",
            "tidal_title": best.name,
            "tidal_artist": best.artist.name if best.artist else "",
        }
    except Exception:
        logger.debug("Tidal search failed for '%s - %s'", artist, title, exc_info=True)
        return None


def search_tracks_batch(
    tracks: list[dict],
    progress_callback: Optional[callable] = None,
) -> list[dict]:
    """Search Tidal for multiple tracks. Returns enriched track dicts.

    Each input dict should have 'artist', 'title' (and optionally other fields).
    Returns the same dicts with 'tidal_id', 'tidal_url', 'tidal_title',
    'tidal_artist' added where found.
    """
    results = []
    for i, track in enumerate(tracks):
        enriched = dict(track)
        match = search_track(track["artist"], track["title"])
        if match:
            enriched.update(match)
        results.append(enriched)
        if progress_callback:
            progress_callback(i + 1, len(tracks))
    return results
