"""Local SQLite cache for Gerbera DLNA library track metadata.

This module provides fast local access to track data by caching Gerbera library
metadata in a SQLite database.
"""

import json
import logging
import random
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from backend.gerbera_client import GerberaTrack

logger = logging.getLogger(__name__)

# Database location
DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "library_cache.db"

# Batch size for sync operations (smaller = more frequent progress updates)
SYNC_BATCH_SIZE = 500

# Module-level sync state (in-memory for progress tracking)
_sync_state = {
    "is_syncing": False,
    "phase": None,  # "fetching_albums", "fetching", or "processing"
    "current": 0,
    "total": 0,
    "error": None,
}

# Lock to prevent race conditions when starting sync
_sync_lock = threading.Lock()

# Track if schema has been initialized
_schema_initialized = False
_schema_lock = threading.Lock()


# =============================================================================
# Gerbera-specific: init_db, sync_tracks, get_tracks
# =============================================================================

IS_LIVE_PATTERN = re.compile(
    r"\b(live|concert|in concert|bootleg|unplugged)\b", re.IGNORECASE
)


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize a Gerbera cache database at the given path.

    Creates the tracks table with Gerbera schema (gerbera_id, file_path,
    play_count; no Plex-specific columns).

    Args:
        db_path: Filesystem path for the SQLite database file.

    Returns:
        Open sqlite3.Connection with row_factory set for dict-like access.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            gerbera_id     INTEGER UNIQUE NOT NULL,
            title          TEXT NOT NULL,
            artist         TEXT NOT NULL,
            album          TEXT NOT NULL,
            genres         TEXT NOT NULL DEFAULT '[]',
            year           INTEGER,
            duration_ms    INTEGER,
            file_path      TEXT NOT NULL,
            play_count     INTEGER DEFAULT 0,
            is_live        BOOLEAN DEFAULT 0,
            first_seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            type       TEXT NOT NULL,
            artist     TEXT NOT NULL,
            album      TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_favorites_artist ON favorites(artist)")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_sync_at TIMESTAMP,
            track_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("INSERT OR IGNORE INTO sync_state (id) VALUES (1)")
    conn.commit()
    return conn


def sync_tracks(conn: sqlite3.Connection, tracks: list[GerberaTrack]) -> None:
    """Insert or update Gerbera tracks in the cache database.

    Uses INSERT ... ON CONFLICT DO UPDATE (upsert) on gerbera_id.
    is_live is auto-detected from title/album keywords.

    Args:
        conn: Open database connection (from init_db).
        tracks: List of GerberaTrack dataclass instances to sync.
    """
    rows = []
    for t in tracks:
        is_live = bool(
            IS_LIVE_PATTERN.search(t.title or "")
            or IS_LIVE_PATTERN.search(t.album or "")
        )
        genres_json = json.dumps([t.genre] if t.genre else [])
        rows.append((
            t.gerbera_id, t.title, t.artist, t.album,
            genres_json, t.year, t.duration_ms,
            t.file_path, t.play_count, is_live,
        ))
    conn.executemany("""
        INSERT INTO tracks
            (gerbera_id, title, artist, album, genres, year,
             duration_ms, file_path, play_count, is_live)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(gerbera_id) DO UPDATE SET
            title=excluded.title, artist=excluded.artist,
            album=excluded.album, genres=excluded.genres,
            year=excluded.year, duration_ms=excluded.duration_ms,
            file_path=excluded.file_path,
            play_count=excluded.play_count, is_live=excluded.is_live
            -- first_seen_at intentionally excluded: preserve original insertion time
    """, rows)
    conn.execute(
        "UPDATE sync_state SET track_count = ?, last_sync_at = CURRENT_TIMESTAMP WHERE id = 1",
        (len(rows),),
    )
    conn.commit()


def get_tracks(
    conn: sqlite3.Connection,
    genres: Optional[list[str]] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_play_count: int = 0,
    exclude_live: bool = False,
) -> list[dict]:
    """Query tracks from the Gerbera cache with optional filters.

    Args:
        conn: Open database connection (from init_db).
        genres: Only return tracks whose genres list contains one of these.
        min_year: Only return tracks from this year or later.
        max_year: Only return tracks from this year or earlier.
        min_play_count: Only return tracks with at least this many plays.
        exclude_live: If True, skip tracks detected as live recordings.

    Returns:
        List of track dicts (all columns from the tracks table).
    """
    query = "SELECT * FROM tracks WHERE 1=1"
    params: list = []

    if genres:
        genre_clauses = " OR ".join(["genres LIKE ?"] * len(genres))
        query += f" AND ({genre_clauses})"
        params.extend([f'%"{g}"%' for g in genres])

    if min_year is not None:
        query += " AND year >= ?"
        params.append(min_year)
    if max_year is not None:
        query += " AND year <= ?"
        params.append(max_year)
    if min_play_count > 0:
        query += " AND play_count >= ?"
        params.append(min_play_count)
    if exclude_live:
        query += " AND is_live = 0"

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


# =============================================================================
# Legacy Plex-based connection helpers (kept for other app functions below)
# =============================================================================


def get_db_connection() -> sqlite3.Connection:
    """Get a database connection with WAL mode enabled.

    Returns:
        sqlite3.Connection with row_factory set for dict-like access
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for concurrent reads during writes
    conn.execute("PRAGMA journal_mode=WAL")
    # Set busy timeout for lock contention
    conn.execute("PRAGMA busy_timeout=5000")
    # Enable foreign keys (good practice)
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


def init_schema(conn: sqlite3.Connection) -> bool:
    """Initialize database schema if not exists.

    Args:
        conn: Database connection

    Returns:
        True if a schema migration was applied (existing tracks need re-sync),
        False if schema was already up-to-date or freshly created.
    """
    conn.executescript("""
        -- Tracks table: cached Gerbera track metadata
        CREATE TABLE IF NOT EXISTS tracks (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            gerbera_id     INTEGER UNIQUE NOT NULL,
            title          TEXT NOT NULL,
            artist         TEXT,
            album          TEXT,
            genres         TEXT,
            year           INTEGER,
            duration_ms    INTEGER,
            file_path      TEXT,
            play_count     INTEGER DEFAULT 0,
            is_live        BOOLEAN DEFAULT 0,
            first_seen_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes for common query patterns
        CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
        CREATE INDEX IF NOT EXISTS idx_tracks_year ON tracks(year);
        CREATE INDEX IF NOT EXISTS idx_tracks_is_live ON tracks(is_live);
        CREATE INDEX IF NOT EXISTS idx_tracks_gerbera_id ON tracks(gerbera_id);

        -- Sync state: single-row metadata table
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            plex_server_id TEXT,
            last_sync_at TIMESTAMP,
            track_count INTEGER DEFAULT 0,
            sync_duration_ms INTEGER
        );

        -- Ensure sync_state has exactly one row
        INSERT OR IGNORE INTO sync_state (id) VALUES (1);

        -- Results table: persistent storage for generated playlists and recommendations
        CREATE TABLE IF NOT EXISTS results (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            prompt TEXT NOT NULL,
            snapshot JSON NOT NULL,
            track_count INTEGER NOT NULL,
            artist TEXT,
            art_rating_key TEXT,
            subtitle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_results_type_created ON results(type, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_results_created_at ON results(created_at DESC);

        -- Favorites: user-marked favorite artists and albums
        CREATE TABLE IF NOT EXISTS favorites (
            type       TEXT NOT NULL,
            artist     TEXT NOT NULL,
            album      TEXT NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(type, artist, album)
        );

        CREATE INDEX IF NOT EXISTS idx_favorites_artist ON favorites(artist);
    """)

    conn.commit()

    # Incremental migration: add first_seen_at if missing (existing databases)
    migration_applied = False
    try:
        conn.execute("ALTER TABLE tracks ADD COLUMN first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        conn.execute("UPDATE tracks SET first_seen_at = CURRENT_TIMESTAMP WHERE first_seen_at IS NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_first_seen ON tracks(first_seen_at)")
        conn.commit()
        migration_applied = True
    except sqlite3.OperationalError:
        pass  # Column already exists — no action needed

    return migration_applied


# Whether a migration was applied on startup (signals need for re-sync)
_migration_applied = False


def ensure_db_initialized() -> sqlite3.Connection:
    """Ensure database exists and schema is initialized.

    Returns:
        Initialized database connection
    """
    global _schema_initialized, _migration_applied
    conn = get_db_connection()

    # Only initialize schema once per process; lock prevents races on startup
    if not _schema_initialized:
        with _schema_lock:
            if not _schema_initialized:
                _migration_applied = init_schema(conn)
                _schema_initialized = True

    return conn


def get_sync_state() -> dict[str, Any]:
    """Get current sync state from database and in-memory state.

    Returns:
        Dict with track_count, synced_at, is_syncing, sync_progress, error
    """
    conn = ensure_db_initialized()
    try:
        row = conn.execute(
            "SELECT plex_server_id, last_sync_at, track_count, sync_duration_ms "
            "FROM sync_state WHERE id = 1"
        ).fetchone()

        # Snapshot sync state under lock for consistent reads
        with _sync_lock:
            ss = dict(_sync_state)

        result = {
            "track_count": row["track_count"] if row else 0,
            "synced_at": row["last_sync_at"] if row else None,
            "plex_server_id": row["plex_server_id"] if row else None,
            "sync_duration_ms": row["sync_duration_ms"] if row else None,
            "is_syncing": ss["is_syncing"],
            "sync_progress": None,
            "error": ss["error"],
        }

        if ss["is_syncing"]:
            result["sync_progress"] = {
                "phase": ss["phase"],
                "current": ss["current"],
                "total": ss["total"],
            }

        return result
    finally:
        conn.close()


def get_cached_tracks() -> list[dict[str, Any]]:
    """Get all tracks from cache.

    Returns:
        List of track dicts with all fields
    """
    conn = ensure_db_initialized()
    try:
        rows = conn.execute(
            "SELECT rating_key, title, artist, album, duration_ms, year, "
            "genres, user_rating, is_live FROM tracks"
        ).fetchall()

        tracks = []
        for row in rows:
            track = dict(row)
            # Parse genres JSON
            if track["genres"]:
                track["genres"] = json.loads(track["genres"])
            else:
                track["genres"] = []
            tracks.append(track)

        return tracks
    finally:
        conn.close()


def get_tracks_by_filters(
    genres: list[str] | None = None,
    decades: list[str] | None = None,
    min_rating: int = 0,
    exclude_live: bool = True,
    limit: int = 0,
) -> list[dict[str, Any]]:
    """Get tracks from cache matching filter criteria.

    Args:
        genres: List of genre names to include (OR matching)
        decades: List of decades like "1990s" (OR matching)
        min_rating: Minimum user rating (0-10, 0 = no filter)
        exclude_live: Whether to exclude live recordings
        limit: Max tracks to return (0 = no limit)

    Returns:
        List of matching track dicts
    """
    conn = ensure_db_initialized()
    try:
        conditions = []
        params: list[Any] = []

        if exclude_live:
            conditions.append("is_live = 0")

        if min_rating > 0:
            conditions.append("user_rating >= ?")
            params.append(min_rating)

        if decades:
            decade_conditions = []
            for decade in decades:
                # Convert "1990s" to year range
                try:
                    start_year = int(decade.rstrip("s"))
                except ValueError:
                    continue
                end_year = start_year + 9
                decade_conditions.append("(year >= ? AND year <= ?)")
                params.extend([start_year, end_year])
            if decade_conditions:
                conditions.append(f"({' OR '.join(decade_conditions)})")

        # Build query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM tracks WHERE {where_clause}"

        # Only apply SQL LIMIT when no genre filter (genre filtering happens in Python)
        # If genres are specified, we need all matching tracks first, then filter, then sample
        if limit > 0 and not genres:
            query += " ORDER BY RANDOM() LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        tracks = []

        for row in rows:
            track = dict(row)
            # Parse genres JSON
            if track["genres"]:
                track["genres"] = json.loads(track["genres"])
            else:
                track["genres"] = []

            # Genre filtering in Python (JSON field doesn't support SQL IN).
            # Substring match so "Rock" matches "Indie Rock" and vice-versa.
            if genres:
                track_genres_lower = [g.lower() for g in track["genres"]]
                requested_lower = [g.lower() for g in genres]
                if not any(
                    any(req in tg or tg in req for req in requested_lower)
                    for tg in track_genres_lower
                ):
                    continue

            tracks.append(track)

        # Apply limit after genre filtering with random sampling
        if limit > 0 and genres and len(tracks) > limit:
            tracks = random.sample(tracks, limit)

        return tracks
    finally:
        conn.close()


def get_new_tracks(limit: int = 300) -> list[dict[str, Any]]:
    """Return the most recently added non-live tracks, newest first.

    Tracks are ordered by first_seen_at DESC so genuinely new additions
    (from syncs after the initial migration) surface first. Falls back to
    id DESC ordering within ties (e.g. right after migration when all rows
    share the same timestamp).
    """
    conn = ensure_db_initialized()
    try:
        rows = conn.execute(
            "SELECT * FROM tracks WHERE is_live = 0 "
            "ORDER BY first_seen_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        tracks = []
        for row in rows:
            track = dict(row)
            track["genres"] = json.loads(track["genres"]) if track.get("genres") else []
            tracks.append(track)
        return tracks
    finally:
        conn.close()


def clear_cache() -> None:
    """Clear all cached tracks and reset sync state."""
    conn = ensure_db_initialized()
    try:
        conn.execute("DELETE FROM tracks")
        conn.execute(
            "UPDATE sync_state SET last_sync_at = NULL, track_count = 0, "
            "sync_duration_ms = NULL WHERE id = 1"
        )
        conn.commit()
        logger.info("Cache cleared")
    finally:
        conn.close()


def is_cache_stale(max_age_hours: int = 24) -> bool:
    """Check if cache is older than max_age_hours.

    Args:
        max_age_hours: Maximum cache age in hours

    Returns:
        True if cache is stale or empty
    """
    state = get_sync_state()
    if not state["synced_at"]:
        return True

    try:
        # Parse ISO timestamp
        synced_at = datetime.fromisoformat(state["synced_at"].replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - synced_at).total_seconds() / 3600
        return age_hours > max_age_hours
    except (ValueError, TypeError):
        return True


def check_server_changed(current_server_id: str) -> bool:
    """Check if Plex server has changed since last sync.

    Args:
        current_server_id: Current Plex server's machineIdentifier

    Returns:
        True if server changed (cache should be cleared)
    """
    state = get_sync_state()
    cached_server_id = state.get("plex_server_id")

    if not cached_server_id:
        return False  # First sync, no change

    return cached_server_id != current_server_id


# sync_library(plex_client, ...) has been removed — replaced by sync_tracks()
# for Gerbera DLNA. plex_client.py will be deleted in a later task.


def get_sync_progress() -> dict[str, Any]:
    """Get current sync progress (for polling).

    Returns:
        Dict with is_syncing, phase, current, total, error
    """
    with _sync_lock:
        return dict(_sync_state)


def count_tracks_by_filters(
    genres: list[str] | None = None,
    decades: list[str] | None = None,
    min_rating: int = 0,
    exclude_live: bool = True,
) -> int:
    """Count tracks matching filter criteria without fetching full data.

    Args:
        genres: List of genre names to include (OR matching)
        decades: List of decades like "1990s" (OR matching)
        min_rating: Minimum user rating (0-10, 0 = no filter)
        exclude_live: Whether to exclude live recordings

    Returns:
        Count of matching tracks, or -1 if cache is empty
    """
    state = get_sync_state()
    if state["track_count"] == 0:
        return -1  # Cache empty, signal to use Plex

    conn = ensure_db_initialized()
    try:
        conditions = []
        params: list[Any] = []

        if exclude_live:
            conditions.append("is_live = 0")

        if min_rating > 0:
            conditions.append("user_rating >= ?")
            params.append(min_rating)

        if decades:
            decade_conditions = []
            for decade in decades:
                try:
                    start_year = int(decade.rstrip("s"))
                except ValueError:
                    continue
                end_year = start_year + 9
                decade_conditions.append("(year >= ? AND year <= ?)")
                params.extend([start_year, end_year])
            if decade_conditions:
                conditions.append(f"({' OR '.join(decade_conditions)})")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # No genre filter - use simple count query
        if not genres:
            query = f"SELECT COUNT(*) FROM tracks WHERE {where_clause}"
            count = conn.execute(query, params).fetchone()[0]
            return count

        # Genre filter - need to check JSON field, so fetch and filter in Python
        query = f"SELECT genres FROM tracks WHERE {where_clause}"
        rows = conn.execute(query, params).fetchall()

        count = 0
        genres_lower = [g.lower() for g in genres]
        for row in rows:
            if row["genres"]:
                track_genres = json.loads(row["genres"])
                track_genres_lower = [g.lower() for g in track_genres]
                if any(g in track_genres_lower for g in genres_lower):
                    count += 1

        return count
    finally:
        conn.close()


def search_tracks(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search tracks by title, artist, or album (case-insensitive).

    Args:
        query: Search string
        limit: Maximum number of results

    Returns:
        List of matching track dicts
    """
    conn = get_db_connection()
    try:
        pattern = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM tracks
               WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
               LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_track_by_key(rating_key: str | int) -> dict[str, Any] | None:
    """Look up a single track by its gerbera_id (rating_key).

    Args:
        rating_key: The gerbera_id of the track

    Returns:
        Track dict or None if not found
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tracks WHERE gerbera_id = ?", (int(rating_key),)
        ).fetchone()
        return dict(row) if row else None
    except (ValueError, TypeError):
        return None
    finally:
        conn.close()


def has_cached_tracks() -> bool:
    """Check if cache has any tracks.

    Returns:
        True if cache is populated
    """
    state = get_sync_state()
    return state["track_count"] > 0


def needs_resync() -> bool:
    """Check if a schema migration was applied that requires a re-sync.

    Returns:
        True if a migration was applied and sync hasn't completed yet.
        Safe for fresh DBs: _migration_applied is False when CREATE TABLE
        already includes all columns (ALTER TABLE no-ops).
    """
    return _migration_applied


def get_album_candidates(
    genres: list[str] | None = None,
    decades: list[str] | None = None,
    exclude_live: bool = True,
) -> list[dict[str, Any]]:
    """Get album candidates aggregated from cached tracks.

    Groups tracks by parent_rating_key to produce album-level data.
    Supports genre/decade filtering.

    Args:
        genres: Optional genre filter (OR matching)
        decades: Optional decade filter (OR matching, e.g. "1990s")
        exclude_live: Exclude live recordings (default True)

    Returns:
        List of album dicts with parent_rating_key, album, album_artist,
        year, genres, decade, track_count, track_rating_keys.
    """
    conn = ensure_db_initialized()
    try:
        conditions = ["parent_rating_key IS NOT NULL", "parent_rating_key != ''"]
        if exclude_live:
            conditions.append("is_live = 0")
        params: list[Any] = []

        if decades:
            decade_conditions = []
            for decade in decades:
                try:
                    start_year = int(decade.rstrip("s"))
                except ValueError:
                    continue
                end_year = start_year + 9
                decade_conditions.append("(year >= ? AND year <= ?)")
                params.extend([start_year, end_year])
            if decade_conditions:
                conditions.append(f"({' OR '.join(decade_conditions)})")

        where_clause = " AND ".join(conditions)
        query = (
            f"SELECT rating_key, title, artist, album, year, genres, parent_rating_key "
            f"FROM tracks WHERE {where_clause} "
            f"ORDER BY parent_rating_key, rating_key"
        )

        rows = conn.execute(query, params).fetchall()

        # Aggregate tracks into albums
        albums: dict[str, dict[str, Any]] = {}
        for row in rows:
            prk = row["parent_rating_key"]
            track_genres = json.loads(row["genres"]) if row["genres"] else []

            if prk not in albums:
                # Derive decade from year
                year = row["year"]
                decade = ""
                if year:
                    decade_start = (year // 10) * 10
                    decade = f"{decade_start}s"

                albums[prk] = {
                    "parent_rating_key": prk,
                    "album": row["album"],
                    # artist column stores grandparentTitle (album artist), not track artist
                    "album_artist": row["artist"],
                    "year": year,
                    "genres": [],
                    "decade": decade,
                    "track_count": 0,
                    "track_rating_keys": [],
                    "_genre_set": set(),
                }

            album = albums[prk]
            album["track_count"] += 1
            album["track_rating_keys"].append(row["rating_key"])
            for g in track_genres:
                if g not in album["_genre_set"]:
                    album["_genre_set"].add(g)
                    album["genres"].append(g)

        # Apply genre filter in Python (genres stored as JSON)
        result = []
        genres_lower = [g.lower() for g in genres] if genres else None
        for album in albums.values():
            # Remove internal tracking set
            del album["_genre_set"]

            if genres_lower:
                album_genres_lower = [g.lower() for g in album["genres"]]
                if not any(g in album_genres_lower for g in genres_lower):
                    continue

            result.append(album)

        return result
    finally:
        conn.close()


def get_cached_genre_decade_stats() -> dict[str, list[dict[str, Any]]]:
    """Get genre and decade stats from the local cache.

    Returns genre/decade lists derived from cached tracks, avoiding a
    round-trip to the Plex server.

    Returns:
        Dict with 'genres' and 'decades' lists, each containing
        {'name': str, 'count': int} dicts sorted by name.
    """
    conn = ensure_db_initialized()
    try:
        rows = conn.execute("SELECT genres, year FROM tracks").fetchall()

        genre_counts: dict[str, int] = {}
        decade_counts: dict[str, int] = {}

        for row in rows:
            # Tally genres
            if row["genres"]:
                for g in json.loads(row["genres"]):
                    genre_counts[g] = genre_counts.get(g, 0) + 1

            # Tally decades
            year = row["year"]
            if year:
                decade_start = (year // 10) * 10
                decade_name = f"{decade_start}s"
                decade_counts[decade_name] = decade_counts.get(decade_name, 0) + 1

        genres = sorted(
            [{"name": name, "count": count} for name, count in genre_counts.items()],
            key=lambda x: x["name"],
        )
        decades = sorted(
            [{"name": name, "count": count} for name, count in decade_counts.items()],
            key=lambda x: x["name"],
        )

        total_tracks = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        return {"genres": genres, "decades": decades, "total_tracks": total_tracks}
    finally:
        conn.close()


def toggle_favorite(
    fav_type: str,
    artist: str,
    album: str = "",
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Toggle a favorite on/off. Returns True if now a favorite, False if removed.

    Args:
        fav_type: 'artist' or 'album'
        artist: Artist name (stored as-is, matched case-insensitively elsewhere)
        album: Album name; empty string for artist-level favorites
        conn: Optional connection (used in tests); opens one if not provided
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        existing = conn.execute(
            "SELECT 1 FROM favorites WHERE type=? AND artist=? AND album=?",
            (fav_type, artist, album),
        ).fetchone()
        if existing:
            conn.execute(
                "DELETE FROM favorites WHERE type=? AND artist=? AND album=?",
                (fav_type, artist, album),
            )
            conn.commit()
            return False
        else:
            conn.execute(
                "INSERT INTO favorites (type, artist, album) VALUES (?, ?, ?)",
                (fav_type, artist, album),
            )
            conn.commit()
            return True
    finally:
        if close_after:
            conn.close()


def get_artists_with_stats(
    days_new: int = 30,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return artists with track count, is_new, is_favorite flags, sorted by track count desc.

    Args:
        days_new: Number of days within which an artist is considered 'new' (first seen).
        conn: Optional connection (used in tests).
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        rows = conn.execute("""
            SELECT
                t.artist,
                COUNT(*) AS track_count,
                MIN(t.first_seen_at) AS first_seen,
                EXISTS(
                    SELECT 1 FROM favorites f
                    WHERE f.type = 'artist' AND LOWER(f.artist) = LOWER(t.artist)
                ) AS is_favorite
            FROM tracks t
            WHERE t.is_live = 0
            GROUP BY t.artist
            ORDER BY track_count DESC
        """).fetchall()
        from datetime import timedelta
        cutoff_dt = datetime.utcnow() - timedelta(days=days_new)
        result = []
        for row in rows:
            first_seen = row["first_seen"]
            try:
                fs_dt = datetime.fromisoformat(first_seen) if first_seen else None
            except (ValueError, TypeError):
                fs_dt = None
            is_new = fs_dt is not None and fs_dt >= cutoff_dt
            result.append({
                "artist": row["artist"],
                "track_count": row["track_count"],
                "is_new": is_new,
                "is_favorite": bool(row["is_favorite"]),
            })
        return result
    finally:
        if close_after:
            conn.close()


def get_albums_with_stats(
    days_new: int = 30,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return albums with track count, is_new, is_favorite flags, sorted by track count desc.

    Args:
        days_new: Number of days within which an album is considered 'new' (first seen).
        conn: Optional connection (used in tests).
    """
    close_after = conn is None
    if conn is None:
        conn = ensure_db_initialized()
    try:
        rows = conn.execute("""
            SELECT
                t.artist,
                t.album,
                COUNT(*) AS track_count,
                MIN(t.first_seen_at) AS first_seen,
                EXISTS(
                    SELECT 1 FROM favorites f
                    WHERE f.type = 'album'
                      AND LOWER(f.artist) = LOWER(t.artist)
                      AND LOWER(f.album)  = LOWER(t.album)
                ) AS is_favorite
            FROM tracks t
            WHERE t.is_live = 0
            GROUP BY t.artist, t.album
            ORDER BY track_count DESC
        """).fetchall()
        from datetime import timedelta
        cutoff_dt = datetime.utcnow() - timedelta(days=days_new)
        result = []
        for row in rows:
            first_seen = row["first_seen"]
            try:
                fs_dt = datetime.fromisoformat(first_seen) if first_seen else None
            except (ValueError, TypeError):
                fs_dt = None
            is_new = fs_dt is not None and fs_dt >= cutoff_dt
            result.append({
                "artist": row["artist"],
                "album": row["album"],
                "track_count": row["track_count"],
                "is_new": is_new,
                "is_favorite": bool(row["is_favorite"]),
            })
        return result
    finally:
        if close_after:
            conn.close()


def get_album_familiarity(
    parent_rating_keys: list[str] | None = None,
) -> dict[str, dict]:
    """Get familiarity data for albums aggregated from cached track play history.

    Classifies each album as:
    - "unplayed": 0 total plays across all tracks
    - "well-loved": avg plays per track >= 3
    - "light": some plays but avg < 3

    Args:
        parent_rating_keys: Optional list of album keys to query.
            If None, returns all albums.

    Returns:
        Dict mapping parent_rating_key -> {"level": str, "last_viewed_at": str|None}
    """
    conn = ensure_db_initialized()
    try:
        query = (
            "SELECT parent_rating_key, "
            "SUM(view_count) AS total_plays, "
            "AVG(view_count) AS avg_plays, "
            "MAX(last_viewed_at) AS last_viewed "
            "FROM tracks "
            "WHERE parent_rating_key IS NOT NULL AND parent_rating_key != '' "
        )
        params: list[str] = []

        if parent_rating_keys is not None:
            placeholders = ",".join("?" for _ in parent_rating_keys)
            query += f"AND parent_rating_key IN ({placeholders}) "
            params.extend(parent_rating_keys)

        query += "GROUP BY parent_rating_key"

        rows = conn.execute(query, params).fetchall()

        result: dict[str, dict] = {}
        for row in rows:
            total_plays = row["total_plays"] or 0
            avg_plays = row["avg_plays"] or 0

            if total_plays == 0:
                level = "unplayed"
            elif avg_plays >= 3:
                level = "well-loved"
            else:
                level = "light"

            result[row["parent_rating_key"]] = {
                "level": level,
                "last_viewed_at": row["last_viewed"],
            }

        return result
    finally:
        conn.close()


# =============================================================================
# Results Persistence
# =============================================================================


def save_result(
    result_type: str,
    title: str,
    prompt: str,
    snapshot: dict,
    track_count: int,
    artist: str | None = None,
    art_rating_key: str | None = None,
    subtitle: str | None = None,
) -> str:
    """Save a generated result and return its unique ID.

    Args:
        result_type: "prompt_playlist", "seed_playlist", or "album_recommendation"
        title: Display title for the result
        prompt: Original user prompt
        snapshot: Full serialized response (GenerateResponse or RecommendGenerateResponse)
        track_count: Number of tracks in the result
        artist: Primary artist (for album recs)
        art_rating_key: Rating key for thumbnail art
        subtitle: Pre-computed subtitle for history feed cards

    Returns:
        16-char hex ID for the saved result
    """
    conn = ensure_db_initialized()
    try:
        # Generate collision-resistant ID with INSERT OR IGNORE to handle
        # concurrent inserts that race past the existence check.
        for _ in range(10):
            result_id = secrets.token_hex(8)
            cursor = conn.execute(
                """INSERT OR IGNORE INTO results (id, type, title, prompt, snapshot, track_count, artist, art_rating_key, subtitle)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (result_id, result_type, title, prompt, json.dumps(snapshot), track_count, artist, art_rating_key, subtitle),
            )
            if cursor.rowcount > 0:
                break
        else:
            raise RuntimeError("Failed to generate unique result ID after 10 attempts")
        conn.commit()
        logger.info("Saved result %s (type=%s, tracks=%d)", result_id, result_type, track_count)
        return result_id
    finally:
        conn.close()


def get_result(result_id: str) -> dict[str, Any] | None:
    """Fetch a single result by ID, including its snapshot.

    Returns:
        Dict with all columns (snapshot parsed from JSON), or None if not found.
    """
    conn = ensure_db_initialized()
    try:
        row = conn.execute(
            "SELECT id, type, title, prompt, snapshot, track_count, artist, art_rating_key, subtitle, created_at FROM results WHERE id = ?",
            (result_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "type": row["type"],
            "title": row["title"],
            "prompt": row["prompt"],
            "snapshot": json.loads(row["snapshot"]),
            "track_count": row["track_count"],
            "artist": row["artist"],
            "art_rating_key": row["art_rating_key"],
            "subtitle": row["subtitle"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def list_results(
    result_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """List results ordered by created_at DESC, without snapshots.

    Args:
        result_type: Optional type filter (can be comma-separated for multiple)
        limit: Max results to return
        offset: Pagination offset

    Returns:
        Tuple of (list of result dicts without snapshot, total count)
    """
    conn = ensure_db_initialized()
    try:
        where_clause = ""
        params: list[Any] = []

        if result_type:
            types = [t.strip() for t in result_type.split(",") if t.strip()]
            placeholders = ",".join("?" for _ in types)
            where_clause = f"WHERE type IN ({placeholders})"
            params = types

        # Get total count
        total = conn.execute(
            f"SELECT COUNT(*) FROM results {where_clause}", params
        ).fetchone()[0]

        # Get page
        rows = conn.execute(
            f"""SELECT id, type, title, prompt, track_count, artist, art_rating_key, subtitle, created_at
                FROM results {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

        results = [
            {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "prompt": row["prompt"],
                "track_count": row["track_count"],
                "artist": row["artist"],
                "art_rating_key": row["art_rating_key"],
                "subtitle": row["subtitle"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        return results, total
    finally:
        conn.close()


def delete_result(result_id: str) -> bool:
    """Delete a result by ID.

    Returns:
        True if a row was deleted, False if not found.
    """
    conn = ensure_db_initialized()
    try:
        cursor = conn.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted result %s", result_id)
        return deleted
    finally:
        conn.close()
